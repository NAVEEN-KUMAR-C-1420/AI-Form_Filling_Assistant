"""
Document Schemas
Pydantic models for document operations
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DocumentTypeEnum(str, Enum):
    """Document type enumeration"""
    AADHAAR = "aadhaar"
    PAN = "pan"
    VOTER_ID = "voter_id"
    RATION_CARD = "ration_card"
    COMMUNITY_CERTIFICATE = "community_certificate"
    INCOME_CERTIFICATE = "income_certificate"
    OTHER = "other"


class EntityTypeEnum(str, Enum):
    """Entity type enumeration"""
    FULL_NAME = "full_name"
    FULL_NAME_REGIONAL = "full_name_regional"  # Name in regional language (Tamil, Hindi, etc.)
    DATE_OF_BIRTH = "date_of_birth"
    GENDER = "gender"
    ADDRESS = "address"
    ADDRESS_REGIONAL = "address_regional"  # Address in regional language
    AADHAAR_NUMBER = "aadhaar_number"
    PAN_NUMBER = "pan_number"
    VOTER_ID_NUMBER = "voter_id_number"
    RATION_CARD_NUMBER = "ration_card_number"
    COMMUNITY = "community"
    ANNUAL_INCOME = "annual_income"
    CERTIFICATE_ISSUE_DATE = "certificate_issue_date"
    FATHER_NAME = "father_name"
    MOTHER_NAME = "mother_name"
    SPOUSE_NAME = "spouse_name"


class DocumentUploadResponse(BaseModel):
    """Response after document upload"""
    document_id: str
    filename: str
    document_type: DocumentTypeEnum
    status: str
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "filename": "aadhaar_card.pdf",
                "document_type": "aadhaar",
                "status": "uploaded",
                "message": "Document uploaded successfully. Ready for extraction."
            }
        }


class ExtractedEntityPreview(BaseModel):
    """Single extracted entity for preview"""
    id: str
    entity_type: EntityTypeEnum
    value: str
    original_language: Optional[str]
    confidence_score: Optional[float]
    needs_review: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "entity-uuid",
                "entity_type": "full_name",
                "value": "Raj Kumar Singh",
                "original_language": "hindi",
                "confidence_score": 0.95,
                "needs_review": False
            }
        }


class ExtractedDataPreview(BaseModel):
    """Preview of all extracted data for user review"""
    document_id: str
    document_type: DocumentTypeEnum
    detected_language: str
    overall_confidence: float
    entities: List[ExtractedEntityPreview]
    warnings: List[str] = []
    extraction_time_ms: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "document_type": "aadhaar",
                "detected_language": "english",
                "overall_confidence": 0.92,
                "entities": [
                    {
                        "id": "entity-1",
                        "entity_type": "full_name",
                        "value": "Raj Kumar",
                        "confidence_score": 0.95
                    }
                ],
                "warnings": ["Low confidence on address field"],
                "extraction_time_ms": 2500
            }
        }


class EntityUpdate(BaseModel):
    """Schema for updating an entity"""
    entity_id: str = Field(..., description="Entity UUID")
    new_value: Optional[str] = Field(None, description="Updated value")
    is_approved: bool = Field(True, description="Whether user approves this entity")
    delete: bool = Field(False, description="Whether to delete this entity")


class ConfirmDataRequest(BaseModel):
    """Request to confirm and save extracted data"""
    document_id: str = Field(..., description="Document UUID")
    entities: List[EntityUpdate] = Field(..., description="List of entity updates")
    consent_given: bool = Field(..., description="User consent to store data")
    consent_text: str = Field(
        default="I confirm that I have reviewed the extracted data and consent to storing it securely.",
        description="Consent text acknowledged by user"
    )
    
    @validator("consent_given")
    def validate_consent(cls, v):
        """Ensure consent is given"""
        if not v:
            raise ValueError("Consent must be given to store data")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "entities": [
                    {"entity_id": "entity-1", "new_value": "Raj Kumar Singh", "is_approved": True},
                    {"entity_id": "entity-2", "is_approved": True},
                    {"entity_id": "entity-3", "delete": True}
                ],
                "consent_given": True,
                "consent_text": "I confirm that I have reviewed the extracted data..."
            }
        }


class DocumentResponse(BaseModel):
    """Full document response"""
    id: str
    document_type: DocumentTypeEnum
    original_filename: str
    status: str
    detected_language: Optional[str]
    ocr_confidence: Optional[float]
    uploaded_at: datetime
    processed_at: Optional[datetime]
    confirmed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ProfileDataResponse(BaseModel):
    """Response for user profile data (all confirmed entities)"""
    user_id: str
    documents: List[DocumentResponse]
    entities: Dict[str, Any]  # Grouped by entity type
    last_updated: Optional[datetime]
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-uuid",
                "documents": [],
                "entities": {
                    "full_name": "Raj Kumar Singh",
                    "date_of_birth": "1990-01-15",
                    "aadhaar_number": "XXXX-XXXX-1234",
                    "address": "123, Main Street, Chennai, Tamil Nadu"
                },
                "last_updated": "2024-01-15T10:30:00Z"
            }
        }


class AutofillRequest(BaseModel):
    """Request for autofill data"""
    website_url: str = Field(..., description="Target website URL")
    form_fields: List[str] = Field(..., description="List of form field identifiers")
    consent_given: bool = Field(..., description="User consent to autofill")
    
    @validator("website_url")
    def validate_https(cls, v):
        """Ensure HTTPS URL"""
        if not v.startswith("https://"):
            raise ValueError("Only HTTPS websites are supported")
        return v
    
    @validator("consent_given")
    def validate_consent(cls, v):
        """Ensure consent is given"""
        if not v:
            raise ValueError("Consent required for autofill")
        return v


class AutofillResponse(BaseModel):
    """Response with autofill data"""
    fields: Dict[str, str]  # field_id -> value
    consent_log_id: str
    expires_at: datetime
