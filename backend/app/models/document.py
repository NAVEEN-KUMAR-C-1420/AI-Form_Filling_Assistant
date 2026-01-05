"""
Document and Extracted Entity Models
Database models for uploaded documents and extracted data
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class DocumentType(str, enum.Enum):
    """Supported document types"""
    AADHAAR = "aadhaar"
    PAN = "pan"
    VOTER_ID = "voter_id"
    DRIVING_LICENSE = "driving_license"
    RATION_CARD = "ration_card"
    COMMUNITY_CERTIFICATE = "community_certificate"
    INCOME_CERTIFICATE = "income_certificate"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    """Document processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class Document(Base):
    """Uploaded document model"""
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Document metadata - using String to match PostgreSQL native enum values (lowercase)
    document_type = Column(String(50), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA-256 hash for integrity
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(String(20), nullable=False)
    
    # Processing info - using String to match PostgreSQL native enum values (lowercase)
    status = Column(String(20), default="uploaded")
    detected_language = Column(String(50), nullable=True)
    ocr_confidence = Column(String(10), nullable=True)  # Stored as string for precision
    processing_error = Column(Text, nullable=True)
    
    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    
    # Soft delete
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="documents")
    extracted_entities = relationship("ExtractedEntity", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document {self.document_type} - {self.id}>"
    
    def to_dict(self):
        """Convert document to dictionary"""
        return {
            "id": str(self.id),
            "document_type": self.document_type,
            "original_filename": self.original_filename,
            "status": self.status,
            "detected_language": self.detected_language,
            "ocr_confidence": self.ocr_confidence,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None
        }


class EntityType(str, enum.Enum):
    """Types of extracted entities"""
    FULL_NAME = "full_name"
    FULL_NAME_REGIONAL = "full_name_regional"  # Name in regional language (Tamil, Hindi, etc.)
    DATE_OF_BIRTH = "date_of_birth"
    GENDER = "gender"
    ADDRESS = "address"
    ADDRESS_REGIONAL = "address_regional"  # Address in regional language
    AADHAAR_NUMBER = "aadhaar_number"
    PAN_NUMBER = "pan_number"
    VOTER_ID_NUMBER = "voter_id_number"
    DRIVING_LICENSE_NUMBER = "driving_license_number"
    RATION_CARD_NUMBER = "ration_card_number"
    COMMUNITY = "community"
    ANNUAL_INCOME = "annual_income"
    CERTIFICATE_ISSUE_DATE = "certificate_issue_date"
    FATHER_NAME = "father_name"
    MOTHER_NAME = "mother_name"
    SPOUSE_NAME = "spouse_name"
    MOBILE_NUMBER = "mobile_number"
    EMAIL = "email"
    BLOOD_GROUP = "blood_group"
    ORGAN_DONOR = "organ_donor"
    VALIDITY_DATE = "validity_date"
    ISSUE_DATE = "issue_date"


class ExtractedEntity(Base):
    """Extracted entity from document"""
    __tablename__ = "extracted_entities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Entity data - using String to match PostgreSQL lowercase enum values
    entity_type = Column(String(50), nullable=False)
    encrypted_value = Column(Text, nullable=False)  # Encrypted at rest
    original_language = Column(String(50), nullable=True)
    translated_value = Column(Text, nullable=True)  # English translation (encrypted)
    
    # Extraction metadata
    confidence_score = Column(String(10), nullable=True)
    extraction_method = Column(String(50), nullable=True)  # regex, ml, manual
    
    # User modifications
    is_user_modified = Column(Boolean, default=False)
    user_modified_at = Column(DateTime, nullable=True)
    
    # Approval status
    is_approved = Column(Boolean, default=False)
    approved_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Soft delete
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    document = relationship("Document", back_populates="extracted_entities")
    
    def __repr__(self):
        return f"<ExtractedEntity {self.entity_type.value} - {self.id}>"
    
    def to_dict(self, decrypted_value: str = None):
        """Convert entity to dictionary"""
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "entity_type": self.entity_type.value,
            "value": decrypted_value,  # Decrypted value passed from service layer
            "original_language": self.original_language,
            "confidence_score": self.confidence_score,
            "is_user_modified": self.is_user_modified,
            "is_approved": self.is_approved,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
