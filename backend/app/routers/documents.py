"""
Documents Router
Endpoints for document upload, extraction, and confirmation
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.document import DocumentType
from app.schemas.document import (
    DocumentUploadResponse, ExtractedDataPreview, ConfirmDataRequest
)
from app.services.document_service import DocumentService
from app.routers.dependencies import get_current_user
from app.utils.file_utils import validate_file, save_temp_file, sanitize_filename


router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    document_type: str = Form(..., description="Type of document (aadhaar, pan, voter_id, etc.)"),
    file: UploadFile = File(..., description="Document image or PDF"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document for processing
    
    **Supported document types:**
    - aadhaar: Aadhaar Card
    - pan: PAN Card
    - voter_id: Voter ID Card
    - ration_card: Ration Card
    - community_certificate: Community/Caste Certificate
    - income_certificate: Income Certificate
    
    **Supported file formats:** JPEG, PNG, TIFF, PDF (max 10MB)
    """
    # Validate document type
    try:
        doc_type = DocumentType(document_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document type. Allowed: {[t.value for t in DocumentType]}"
        )
    
    # Validate file
    is_valid, error_msg = await validate_file(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Sanitize filename
    safe_filename = sanitize_filename(file.filename)
    
    # Save to temp storage
    file_path, file_hash, file_size = await save_temp_file(file, str(current_user.id))
    
    # Create document record
    document_service = DocumentService(db)
    document = await document_service.create_document(
        user_id=current_user.id,
        document_type=doc_type,
        filename=safe_filename,
        file_hash=file_hash,
        mime_type=file.content_type,
        file_size=file_size
    )
    
    return DocumentUploadResponse(
        document_id=str(document.id),
        filename=safe_filename,
        document_type=doc_type,
        status=document.status,
        message="Document uploaded successfully. Use /documents/extract to process."
    )


@router.post("/extract", response_model=ExtractedDataPreview)
async def extract_document_data(
    document_id: str = Form(..., description="Document UUID from upload"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Extract data from uploaded document using OCR
    
    **Important:** This returns extracted data for PREVIEW only.
    Data is NOT stored until user confirms via /documents/confirm endpoint.
    
    The response includes:
    - Extracted entities (name, DOB, ID numbers, etc.)
    - Confidence scores for each field
    - Warnings for low-confidence extractions
    """
    document_service = DocumentService(db)
    
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format"
        )
    
    # Get document
    document = await document_service.get_document(doc_uuid, current_user.id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Build file path
    from pathlib import Path
    from app.config import settings
    
    # Find the temp file
    user_dir = Path(settings.TEMP_UPLOAD_DIR) / str(current_user.id)
    file_path = None
    
    if user_dir.exists():
        for f in user_dir.iterdir():
            if f.is_file():
                file_path = str(f)
                break
    
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found. Please re-upload."
        )
    
    try:
        preview = await document_service.process_document(doc_uuid, file_path, current_user.id)
        return preview
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.post("/confirm")
async def confirm_extracted_data(
    request: ConfirmDataRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Confirm and save extracted data after user review
    
    **CRITICAL CONSENT STEP**
    
    This endpoint:
    1. Requires explicit user consent
    2. Allows user to modify extracted values
    3. Allows user to delete unwanted fields
    4. Encrypts and stores approved data
    5. Logs consent for audit trail
    
    **Request body:**
    - document_id: UUID of the processed document
    - entities: List of entity updates with approval status
    - consent_given: MUST be true
    - consent_text: Consent acknowledgment text
    """
    document_service = DocumentService(db)
    
    try:
        result = await document_service.confirm_extracted_data(current_user.id, request)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/list")
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all documents uploaded by the user
    """
    from sqlalchemy import select
    from app.models.document import Document
    
    result = await db.execute(
        select(Document).where(
            Document.user_id == current_user.id,
            Document.is_deleted == False
        ).order_by(Document.uploaded_at.desc())
    )
    documents = result.scalars().all()
    
    return {
        "total": len(documents),
        "documents": [doc.to_dict() for doc in documents]
    }


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete a document and its extracted entities
    """
    from datetime import datetime
    from sqlalchemy import update
    from app.models.document import Document, ExtractedEntity
    
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format"
        )
    
    # Verify ownership
    document_service = DocumentService(db)
    document = await document_service.get_document(doc_uuid, current_user.id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Soft delete document
    await db.execute(
        update(Document).where(Document.id == doc_uuid).values(
            is_deleted=True,
            deleted_at=datetime.utcnow()
        )
    )
    
    # Soft delete entities
    await db.execute(
        update(ExtractedEntity).where(ExtractedEntity.document_id == doc_uuid).values(
            is_deleted=True,
            deleted_at=datetime.utcnow()
        )
    )
    
    await db.commit()
    
    return {"message": "Document deleted successfully"}
