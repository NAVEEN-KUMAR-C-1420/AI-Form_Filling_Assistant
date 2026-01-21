"""
Consent Schemas
Pydantic models for consent logging
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ConsentActionEnum(str, Enum):
    """Consent action types"""
    DOCUMENT_UPLOAD = "document_upload"
    DATA_EXTRACTION = "data_extraction"
    DATA_STORAGE = "data_storage"
    DATA_MODIFICATION = "data_modification"
    AUTOFILL_REQUEST = "autofill_request"
    FORM_SUBMISSION = "form_submission"
    DATA_DELETION = "data_deletion"
    DATA_EXPORT = "data_export"
    VOICE_INPUT = "voice_input"


class ConsentRequest(BaseModel):
    """Request to log consent"""
    action: ConsentActionEnum = Field(..., description="Type of action")
    consent_given: bool = Field(..., description="Whether consent was given")
    consent_text: Optional[str] = Field(None, description="Consent text shown to user")
    document_id: Optional[str] = Field(None, description="Related document ID")
    target_website: Optional[str] = Field(None, description="Target website for autofill")
    form_fields: Optional[List[str]] = Field(None, description="Form fields involved")
    additional_data: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "action": "autofill_request",
                "consent_given": True,
                "consent_text": "I agree to autofill this form with my saved data",
                "target_website": "https://www.india.gov.in/form",
                "form_fields": ["name", "dob", "address"]
            }
        }


class ConsentLogResponse(BaseModel):
    """Response for consent log"""
    id: str
    action: ConsentActionEnum
    consent_given: bool
    consent_text: Optional[str]
    document_id: Optional[str]
    target_website: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConsentHistoryResponse(BaseModel):
    """Response for consent history"""
    total: int
    page: int
    per_page: int
    logs: List[ConsentLogResponse]
