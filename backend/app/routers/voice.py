"""
Voice Input Router
Endpoints for voice-to-text processing
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.consent_log import ConsentLog
from app.schemas.voice import VoiceInputRequest, VoiceInputResponse, VoiceApprovalRequest
from app.services.voice_service import VoiceInputService
from app.routers.dependencies import get_current_user


router = APIRouter()


@router.post("", response_model=VoiceInputResponse)
async def process_voice_input(
    request: VoiceInputRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Process voice input and return recognized text
    
    **Important:** The recognized text is returned for PREVIEW.
    User must explicitly approve before applying to any field.
    
    **Request:**
    - audio_data: Base64 encoded WAV audio
    - language: Voice language (en-IN, hi-IN, ta-IN, te-IN, kn-IN, ml-IN)
    - target_field: The form field this voice input is for
    
    **Response:**
    - recognized_text: Main recognition result
    - confidence: Confidence score (0-1)
    - alternatives: Alternative transcriptions
    - requires_approval: Always true (user must approve)
    """
    voice_service = VoiceInputService()
    
    try:
        result = await voice_service.process_voice_input(
            request.audio_data,
            request.language,
            request.target_field
        )
        
        # Log voice input consent
        consent_log = ConsentLog(
            user_id=current_user.id,
            action="voice_input",
            consent_given=True,
            consent_text=f"Voice input processed for field: {request.target_field}",
            additional_data={
                "target_field": request.target_field,
                "language": request.language.value,
                "recognized_text": result.recognized_text[:100] if result.success else None,
                "confidence": result.confidence
            }
        )
        db.add(consent_log)
        await db.commit()
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.post("/approve")
async def approve_voice_input(
    request: VoiceApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Approve voice input for applying to a field
    
    This endpoint logs user's approval of the voice-recognized text.
    The actual field update is handled by the Chrome extension.
    
    **Request:**
    - recognized_text: The text being approved
    - target_field: The field to apply it to
    - approved: User's approval decision
    """
    # Log approval consent
    consent_log = ConsentLog(
        user_id=current_user.id,
        action="data_modification",
        consent_given=request.approved,
        consent_text=f"Voice input {'approved' if request.approved else 'rejected'} for field: {request.target_field}",
        additional_data={
            "target_field": request.target_field,
            "recognized_text": request.recognized_text[:100],
            "approved": request.approved
        }
    )
    db.add(consent_log)
    await db.commit()
    
    return {
        "success": True,
        "approved": request.approved,
        "target_field": request.target_field,
        "message": f"Voice input {'approved and ready to apply' if request.approved else 'rejected'}"
    }


@router.get("/languages")
async def get_supported_languages():
    """
    Get list of supported voice input languages
    """
    from app.schemas.voice import SupportedLanguage
    
    languages = [
        {"code": lang.value, "name": lang.name.replace("_", " ").title()}
        for lang in SupportedLanguage
    ]
    
    return {"languages": languages}
