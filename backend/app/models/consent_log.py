"""
Consent Log Model
Database model for tracking user consent and audit trail
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ConsentLog(Base):
    """Consent and audit log model"""
    __tablename__ = "consent_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Consent details
    action = Column(String(50), nullable=False)
    consent_given = Column(Boolean, nullable=False)
    consent_text = Column(Text, nullable=True)  # The consent message shown to user
    
    # Context
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    target_website = Column(String(500), nullable=True)  # For autofill consent
    form_fields = Column(JSON, nullable=True)  # Fields involved in the action
    
    # Request metadata
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(36), nullable=True)
    
    # Additional data
    additional_data = Column(JSON, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="consent_logs")
    
    def __repr__(self):
        return f"<ConsentLog {self.action} - {self.id}>"
    
    def to_dict(self):
        """Convert consent log to dictionary"""
        return {
            "id": str(self.id),
            "action": self.action,
            "consent_given": self.consent_given,
            "consent_text": self.consent_text,
            "document_id": str(self.document_id) if self.document_id else None,
            "target_website": self.target_website,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
