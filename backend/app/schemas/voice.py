"""
Voice Input Schemas
Pydantic models for voice input processing
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import Enum


class SupportedLanguage(str, Enum):
    """Supported voice input languages"""
    ENGLISH = "en-IN"
    HINDI = "hi-IN"
    TAMIL = "ta-IN"
    TELUGU = "te-IN"
    KANNADA = "kn-IN"
    MALAYALAM = "ml-IN"


class VoiceInputRequest(BaseModel):
    """Request for voice input processing"""
    audio_data: str = Field(..., description="Base64 encoded audio data")
    language: SupportedLanguage = Field(default=SupportedLanguage.ENGLISH, description="Voice language")
    target_field: str = Field(..., description="Target form field to update")
    
    @validator("audio_data")
    def validate_audio_data(cls, v):
        """Validate audio data is not empty"""
        if not v or len(v) < 100:  # Minimum base64 length
            raise ValueError("Invalid audio data")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "audio_data": "base64_encoded_audio_string...",
                "language": "en-IN",
                "target_field": "full_name"
            }
        }


class VoiceInputResponse(BaseModel):
    """Response for voice input"""
    success: bool
    recognized_text: str
    confidence: float
    language_detected: str
    alternatives: List[str] = []
    requires_approval: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "recognized_text": "Raj Kumar Singh",
                "confidence": 0.92,
                "language_detected": "en-IN",
                "alternatives": ["Raj Kumar", "Raj Kumar Sinha"],
                "requires_approval": True
            }
        }


class VoiceApprovalRequest(BaseModel):
    """Request to approve voice input"""
    recognized_text: str = Field(..., description="Text to apply")
    target_field: str = Field(..., description="Target form field")
    approved: bool = Field(..., description="User approval")
    
    class Config:
        json_schema_extra = {
            "example": {
                "recognized_text": "Raj Kumar Singh",
                "target_field": "full_name",
                "approved": True
            }
        }
