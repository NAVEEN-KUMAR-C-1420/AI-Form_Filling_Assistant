"""
User Router
Endpoints for user profile and data management
"""
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.auth import UserResponse
from app.services.document_service import DocumentService
from app.services.auth_service import AuthService
from app.routers.dependencies import get_current_user


router = APIRouter()


class AutofillRequest(BaseModel):
    """Request model for autofill data"""
    fields: List[str]
    website_url: str


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user's profile
    """
    return current_user.to_dict()


@router.get("/profile-data")
async def get_profile_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all confirmed profile data for autofill
    
    Returns:
    - List of uploaded documents
    - All confirmed entities grouped by type
    - Sensitive values are masked (only last 4 digits shown)
    
    Use /user/autofill endpoint to get full values for autofill
    """
    document_service = DocumentService(db)
    profile_data = await document_service.get_user_profile_data(current_user.id)
    return profile_data


@router.post("/autofill")
async def get_autofill_data(
    request: AutofillRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get decrypted data for autofill (Chrome extension use)
    
    **Security requirements:**
    - Only HTTPS websites allowed
    - User must have confirmed the data
    - Consent is logged
    
    **Request:**
    - fields: List of field names needed (e.g., ["name", "dob", "address"])
    - website_url: Target website URL (must be HTTPS)
    """
    fields = request.fields
    website_url = request.website_url
    
    # Validate HTTPS
    if not website_url.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only HTTPS websites are supported for autofill"
        )
    
    document_service = DocumentService(db)
    
    # Log consent for autofill
    from app.models.consent_log import ConsentLog
    consent_log = ConsentLog(
        user_id=current_user.id,
        action="autofill_request",
        consent_given=True,
        consent_text="User requested autofill data",
        target_website=website_url,
        form_fields=fields
    )
    db.add(consent_log)
    await db.commit()
    
    # Get autofill data
    autofill_data = await document_service.get_autofill_data(current_user.id, fields)
    
    return {
        "fields": autofill_data,
        "consent_log_id": str(consent_log.id),
        "website": website_url
    }


@router.delete("/data/field/{field_type}")
async def delete_single_field(
    field_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a single field from user's saved data
    
    **Parameters:**
    - field_type: Type of field to delete (e.g., full_name, date_of_birth, etc.)
    """
    document_service = DocumentService(db)
    result = await document_service.delete_field(current_user.id, field_type)
    
    if result["deleted"] == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for field: {field_type}"
        )
    
    return {
        "message": f"Field '{field_type}' deleted successfully",
        "deleted": result["deleted"]
    }


@router.put("/data/entity/{entity_id}")
async def update_entity(
    entity_id: str,
    new_value: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a single entity's value
    
    **Parameters:**
    - entity_id: UUID of the entity to update
    - new_value: New value for the entity
    """
    document_service = DocumentService(db)
    
    try:
        result = await document_service.update_entity(current_user.id, entity_id, new_value)
        return {
            "message": "Entity updated successfully",
            "entity_id": entity_id,
            "updated": True
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/data/entity/{entity_id}")
async def delete_entity(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a single entity by ID
    
    **Parameters:**
    - entity_id: UUID of the entity to delete
    """
    document_service = DocumentService(db)
    
    try:
        result = await document_service.delete_entity(current_user.id, entity_id)
        return {
            "message": "Entity deleted successfully",
            "entity_id": entity_id,
            "deleted": True
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/data")
async def delete_all_user_data(
    confirm: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Permanently delete ALL user data
    
    **WARNING:** This action is irreversible!
    
    Deletes:
    - All uploaded documents
    - All extracted entities
    - All profile data
    
    User account remains active but empty.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must confirm deletion by setting confirm=true"
        )
    
    document_service = DocumentService(db)
    result = await document_service.delete_user_data(current_user.id)
    
    return {
        "message": "All user data permanently deleted",
        **result
    }


@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change user password
    
    **Requirements:**
    - Current password must be correct
    - New password must meet strength requirements
    """
    auth_service = AuthService(db)
    
    success, message = await auth_service.change_password(
        current_user.id, old_password, new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {"message": message}


@router.delete("/account")
async def delete_account(
    password: str,
    confirm: bool,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Permanently delete user account
    
    **WARNING:** This action is irreversible!
    
    Requires password confirmation and explicit confirm flag.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must confirm account deletion by setting confirm=true"
        )
    
    # Verify password
    from app.utils.security import verify_password
    if not verify_password(password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )
    
    # Delete all user data first
    document_service = DocumentService(db)
    await document_service.delete_user_data(current_user.id)
    
    # Deactivate account
    auth_service = AuthService(db)
    await auth_service.deactivate_user(current_user.id)
    
    return {"message": "Account permanently deleted"}


@router.get("/consent-history")
async def get_consent_history(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's consent history (audit trail)
    
    Returns all consent actions logged for the user.
    """
    from sqlalchemy import select, func
    from app.models.consent_log import ConsentLog
    
    # Count total
    count_result = await db.execute(
        select(func.count(ConsentLog.id)).where(ConsentLog.user_id == current_user.id)
    )
    total = count_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * per_page
    result = await db.execute(
        select(ConsentLog)
        .where(ConsentLog.user_id == current_user.id)
        .order_by(ConsentLog.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    logs = result.scalars().all()
    
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "logs": [log.to_dict() for log in logs]
    }
