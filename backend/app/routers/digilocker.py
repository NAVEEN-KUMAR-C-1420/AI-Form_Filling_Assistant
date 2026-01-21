"""
DigiLocker Routes
API endpoints for DigiLocker OAuth and document fetching
"""
import secrets
import base64
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db
from app.models.user import User
from app.models.document import Document, ExtractedEntity, DocumentType, DocumentStatus, EntityType
from app.routers.dependencies import get_current_user
from app.services.digilocker_service import digilocker_service
from app.schemas.digilocker import (
    DigiLockerAuthRequest, DigiLockerAuthResponse,
    DigiLockerCallbackRequest, DigiLockerTokenResponse,
    DigiLockerDocumentsResponse, DigiLockerDocument,
    DigiLockerPullRequest, DigiLockerExtractedData,
    DigiLockerConnectionStatus, DigiLockerDisconnectResponse,
    DigiLockerImportRequest, DigiLockerImportResponse
)
from app.utils.security import encrypt_value

router = APIRouter(prefix="/digilocker", tags=["DigiLocker Integration"])

# In-memory storage for OAuth state (use Redis in production)
oauth_states = {}


@router.post("/auth/initiate", response_model=DigiLockerAuthResponse)
async def initiate_digilocker_auth(
    request: DigiLockerAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate DigiLocker OAuth2 flow
    Returns authorization URL for user to login
    """
    try:
        # Generate state and code verifier
        state = secrets.token_urlsafe(32)
        code_verifier = digilocker_service.generate_code_verifier()
        
        # Get authorization URL
        auth_data = digilocker_service.get_authorization_url(state, code_verifier)
        
        # Store state and verifier for callback verification
        oauth_states[state] = {
            "user_id": str(current_user.id),
            "code_verifier": code_verifier,
            "created_at": datetime.utcnow(),
            "redirect_url": request.redirect_url
        }
        
        logger.info(f"DigiLocker auth initiated for user {current_user.id}")
        
        return DigiLockerAuthResponse(
            auth_url=auth_data["auth_url"],
            state=state
        )
        
    except Exception as e:
        logger.exception(f"Error initiating DigiLocker auth: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate DigiLocker authentication"
        )


@router.get("/auth/callback")
async def digilocker_callback(
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle DigiLocker OAuth callback
    Exchange authorization code for tokens
    """
    try:
        # Verify state
        if state not in oauth_states:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state parameter"
            )
        
        state_data = oauth_states.pop(state)
        
        # Check state expiry (10 minutes)
        if datetime.utcnow() - state_data["created_at"] > timedelta(minutes=10):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="State parameter expired"
            )
        
        # Exchange code for tokens
        token_response = await digilocker_service.exchange_code_for_token(
            code=code,
            code_verifier=state_data["code_verifier"]
        )
        
        if not token_response.get("success"):
            error_msg = token_response.get("error", "Token exchange failed")
            logger.error(f"DigiLocker token exchange failed: {error_msg}")
            
            # Redirect back to extension with error
            if state_data.get("redirect_url"):
                return RedirectResponse(
                    url=f"{state_data['redirect_url']}?error={error_msg}"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Get user and update DigiLocker connection
        user_id = state_data["user_id"]
        result = await db.execute(
            User.__table__.select().where(User.id == user_id)
        )
        user = result.fetchone()
        
        if user:
            # Store encrypted tokens
            await db.execute(
                User.__table__.update()
                .where(User.id == user_id)
                .values(
                    digilocker_access_token=encrypt_value(token_response.get("access_token", "")),
                    digilocker_refresh_token=encrypt_value(token_response.get("refresh_token", "")),
                    digilocker_id=token_response.get("digilocker_id"),
                    digilocker_name=token_response.get("name"),
                    digilocker_connected_at=datetime.utcnow(),
                    digilocker_token_expires_at=datetime.utcnow() + timedelta(
                        seconds=token_response.get("expires_in", 3600)
                    )
                )
            )
            await db.commit()
            
        logger.info(f"DigiLocker connected for user {user_id}")
        
        # Redirect back to extension
        if state_data.get("redirect_url"):
            return RedirectResponse(
                url=f"{state_data['redirect_url']}?success=true&name={token_response.get('name', '')}"
            )
        
        return {
            "success": True,
            "message": "DigiLocker connected successfully",
            "name": token_response.get("name")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in DigiLocker callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete DigiLocker authentication"
        )


@router.post("/auth/callback", response_model=DigiLockerTokenResponse)
async def digilocker_callback_post(
    request: DigiLockerCallbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle DigiLocker OAuth callback (POST method for extension)
    """
    try:
        # Verify state
        if request.state not in oauth_states:
            return DigiLockerTokenResponse(
                success=False,
                error="Invalid or expired state parameter"
            )
        
        state_data = oauth_states.pop(request.state)
        
        # Verify user matches
        if state_data["user_id"] != str(current_user.id):
            return DigiLockerTokenResponse(
                success=False,
                error="User mismatch"
            )
        
        # Exchange code for tokens
        token_response = await digilocker_service.exchange_code_for_token(
            code=request.code,
            code_verifier=state_data["code_verifier"]
        )
        
        if token_response.get("success"):
            # Store tokens (encrypted)
            current_user.digilocker_access_token = encrypt_value(
                token_response.get("access_token", "")
            )
            current_user.digilocker_refresh_token = encrypt_value(
                token_response.get("refresh_token", "")
            )
            current_user.digilocker_id = token_response.get("digilocker_id")
            current_user.digilocker_name = token_response.get("name")
            current_user.digilocker_connected_at = datetime.utcnow()
            current_user.digilocker_token_expires_at = datetime.utcnow() + timedelta(
                seconds=token_response.get("expires_in", 3600)
            )
            
            await db.commit()
            
        return DigiLockerTokenResponse(
            success=token_response.get("success", False),
            access_token=None,  # Don't expose token to client
            digilocker_id=token_response.get("digilocker_id"),
            name=token_response.get("name"),
            error=token_response.get("error")
        )
        
    except Exception as e:
        logger.exception(f"Error in callback: {e}")
        return DigiLockerTokenResponse(
            success=False,
            error=str(e)
        )


@router.get("/status", response_model=DigiLockerConnectionStatus)
async def get_digilocker_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get DigiLocker connection status for current user
    """
    connected = bool(
        current_user.digilocker_access_token and 
        current_user.digilocker_connected_at
    )
    
    # Check if token expired
    if connected and current_user.digilocker_token_expires_at:
        if datetime.utcnow() > current_user.digilocker_token_expires_at:
            connected = False
    
    return DigiLockerConnectionStatus(
        connected=connected,
        digilocker_id=current_user.digilocker_id if connected else None,
        name=current_user.digilocker_name if connected else None,
        connected_at=current_user.digilocker_connected_at if connected else None,
        expires_at=current_user.digilocker_token_expires_at if connected else None
    )


@router.post("/disconnect", response_model=DigiLockerDisconnectResponse)
async def disconnect_digilocker(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect DigiLocker from user account
    """
    try:
        current_user.digilocker_access_token = None
        current_user.digilocker_refresh_token = None
        current_user.digilocker_id = None
        current_user.digilocker_name = None
        current_user.digilocker_connected_at = None
        current_user.digilocker_token_expires_at = None
        
        await db.commit()
        
        logger.info(f"DigiLocker disconnected for user {current_user.id}")
        
        return DigiLockerDisconnectResponse(
            success=True,
            message="DigiLocker disconnected successfully"
        )
        
    except Exception as e:
        logger.exception(f"Error disconnecting DigiLocker: {e}")
        return DigiLockerDisconnectResponse(
            success=False,
            message=f"Failed to disconnect: {str(e)}"
        )


@router.get("/documents", response_model=DigiLockerDocumentsResponse)
async def get_digilocker_documents(
    current_user: User = Depends(get_current_user)
):
    """
    Fetch list of documents from user's DigiLocker
    """
    # Check if connected
    if not current_user.digilocker_access_token:
        return DigiLockerDocumentsResponse(
            success=False,
            error="DigiLocker not connected. Please connect first."
        )
    
    try:
        from app.utils.security import decrypt_value
        access_token = decrypt_value(current_user.digilocker_access_token)
        
        # Check if token expired and try refresh
        if current_user.digilocker_token_expires_at:
            if datetime.utcnow() > current_user.digilocker_token_expires_at:
                # Try to refresh token
                if current_user.digilocker_refresh_token:
                    refresh_token = decrypt_value(current_user.digilocker_refresh_token)
                    refresh_result = await digilocker_service.refresh_access_token(refresh_token)
                    
                    if refresh_result.get("success"):
                        access_token = refresh_result.get("access_token")
                        # Update stored token
                        current_user.digilocker_access_token = encrypt_value(access_token)
                        current_user.digilocker_token_expires_at = datetime.utcnow() + timedelta(
                            seconds=refresh_result.get("expires_in", 3600)
                        )
                    else:
                        return DigiLockerDocumentsResponse(
                            success=False,
                            error="DigiLocker session expired. Please reconnect."
                        )
        
        # Fetch documents
        result = await digilocker_service.get_issued_documents(access_token)
        
        if result.get("success"):
            documents = [
                DigiLockerDocument(**doc) 
                for doc in result.get("documents", [])
            ]
            return DigiLockerDocumentsResponse(
                success=True,
                documents=documents,
                total=len(documents)
            )
        else:
            return DigiLockerDocumentsResponse(
                success=False,
                error=result.get("error", "Failed to fetch documents")
            )
            
    except Exception as e:
        logger.exception(f"Error fetching DigiLocker documents: {e}")
        return DigiLockerDocumentsResponse(
            success=False,
            error=str(e)
        )


@router.post("/pull", response_model=DigiLockerExtractedData)
async def pull_document(
    request: DigiLockerPullRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Pull and extract data from a specific DigiLocker document
    """
    if not current_user.digilocker_access_token:
        return DigiLockerExtractedData(
            success=False,
            doc_type="unknown",
            error="DigiLocker not connected"
        )
    
    try:
        from app.utils.security import decrypt_value
        access_token = decrypt_value(current_user.digilocker_access_token)
        
        # Pull document
        result = await digilocker_service.pull_document(
            access_token=access_token,
            uri=request.uri,
            doc_type=request.doc_type
        )
        
        if not result.get("success"):
            return DigiLockerExtractedData(
                success=False,
                doc_type=request.doc_type or "unknown",
                error=result.get("error")
            )
        
        # If document needs OCR (PDF/image), process it
        if result.get("needs_ocr"):
            # Save to temp file and run OCR
            from app.services.ocr_service import ocr_service
            import tempfile
            import os
            
            content = base64.b64decode(result.get("data", ""))
            doc_type_enum = getattr(DocumentType, request.doc_type.upper(), DocumentType.AADHAAR)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
                f.write(content)
                temp_path = f.name
            
            try:
                ocr_result = await ocr_service.process_document(temp_path, doc_type_enum)
                entities = ocr_result.get("entities", [])
            finally:
                os.unlink(temp_path)
            
            return DigiLockerExtractedData(
                success=True,
                doc_type=request.doc_type,
                source="digilocker_ocr",
                entities=entities,
                needs_ocr=False
            )
        
        # Return structured data
        return DigiLockerExtractedData(
            success=True,
            doc_type=result.get("doc_type", request.doc_type),
            source=result.get("source", "digilocker"),
            entities=result.get("entities", []),
            needs_ocr=False
        )
        
    except Exception as e:
        logger.exception(f"Error pulling document: {e}")
        return DigiLockerExtractedData(
            success=False,
            doc_type=request.doc_type or "unknown",
            error=str(e)
        )


@router.post("/import", response_model=DigiLockerImportResponse)
async def import_documents(
    request: DigiLockerImportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Import selected documents from DigiLocker and save extracted data
    """
    if not current_user.digilocker_access_token:
        return DigiLockerImportResponse(
            success=False,
            error="DigiLocker not connected"
        )
    
    try:
        from app.utils.security import decrypt_value
        access_token = decrypt_value(current_user.digilocker_access_token)
        
        imported = 0
        failed = 0
        results = []
        
        # First get document list to map URIs to types
        docs_result = await digilocker_service.get_issued_documents(access_token)
        doc_map = {d["uri"]: d for d in docs_result.get("documents", [])}
        
        for uri in request.document_uris:
            try:
                doc_info = doc_map.get(uri, {})
                doc_type = doc_info.get("doc_type", "aadhaar")
                
                # Pull and extract document
                result = await digilocker_service.pull_document(
                    access_token=access_token,
                    uri=uri,
                    doc_type=doc_type
                )
                
                if not result.get("success"):
                    failed += 1
                    results.append({
                        "uri": uri,
                        "success": False,
                        "error": result.get("error")
                    })
                    continue
                
                # Map to our document type enum
                doc_type_enum = DocumentType.AADHAAR  # Default
                type_mapping = {
                    "aadhaar": DocumentType.AADHAAR,
                    "pan": DocumentType.PAN,
                    "driving_license": DocumentType.DRIVING_LICENSE,
                    "voter_id": DocumentType.VOTER_ID,
                    "income_certificate": DocumentType.INCOME_CERTIFICATE,
                    "community_certificate": DocumentType.COMMUNITY_CERTIFICATE,
                }
                doc_type_enum = type_mapping.get(doc_type, DocumentType.AADHAAR)
                
                # Create document record
                document = Document(
                    user_id=current_user.id,
                    document_type=doc_type_enum,
                    original_filename=f"digilocker_{doc_info.get('name', uri)}",
                    file_hash=f"digilocker:{uri}",
                    mime_type=doc_info.get("mime_type", "application/pdf"),
                    status=DocumentStatus.EXTRACTED,
                    detected_language="en",
                    ocr_confidence="1.0",
                    processed_at=datetime.utcnow()
                )
                db.add(document)
                await db.flush()
                
                # Save extracted entities
                entities = result.get("entities", [])
                for entity_data in entities:
                    entity_type_str = entity_data.get("entity_type", "").upper()
                    entity_type = getattr(EntityType, entity_type_str, None)
                    
                    if entity_type:
                        entity = ExtractedEntity(
                            document_id=document.id,
                            user_id=current_user.id,
                            entity_type=entity_type,
                            encrypted_value=encrypt_value(entity_data.get("value", "")),
                            original_language=entity_data.get("original_language", "en"),
                            confidence_score=str(entity_data.get("confidence_score", 1.0)),
                            extraction_method=entity_data.get("extraction_method", "digilocker_api"),
                            is_approved=True,  # Auto-approve DigiLocker data
                            approved_at=datetime.utcnow()
                        )
                        db.add(entity)
                
                await db.commit()
                imported += 1
                results.append({
                    "uri": uri,
                    "success": True,
                    "document_id": str(document.id),
                    "doc_type": doc_type,
                    "entities_count": len(entities)
                })
                
            except Exception as e:
                logger.exception(f"Error importing document {uri}: {e}")
                failed += 1
                results.append({
                    "uri": uri,
                    "success": False,
                    "error": str(e)
                })
        
        return DigiLockerImportResponse(
            success=imported > 0,
            imported=imported,
            failed=failed,
            results=results
        )
        
    except Exception as e:
        logger.exception(f"Error in import: {e}")
        return DigiLockerImportResponse(
            success=False,
            error=str(e)
        )


@router.get("/eaadhaar", response_model=DigiLockerExtractedData)
async def get_eaadhaar(
    current_user: User = Depends(get_current_user)
):
    """
    Fetch eAadhaar directly from DigiLocker (structured XML data)
    """
    if not current_user.digilocker_access_token:
        return DigiLockerExtractedData(
            success=False,
            doc_type="aadhaar",
            error="DigiLocker not connected"
        )
    
    try:
        from app.utils.security import decrypt_value
        access_token = decrypt_value(current_user.digilocker_access_token)
        
        result = await digilocker_service.get_eaadhaar(access_token)
        
        return DigiLockerExtractedData(
            success=result.get("success", False),
            doc_type="aadhaar",
            source="digilocker_eaadhaar",
            entities=result.get("entities", []),
            needs_ocr=False,
            error=result.get("error")
        )
        
    except Exception as e:
        logger.exception(f"Error fetching eAadhaar: {e}")
        return DigiLockerExtractedData(
            success=False,
            doc_type="aadhaar",
            error=str(e)
        )
