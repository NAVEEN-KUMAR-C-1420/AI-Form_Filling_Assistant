"""
User Model
Database model for user accounts with security features
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """User account model"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone_number = Column(String(15), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # Security fields
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    failed_login_attempts = Column(String(5), default="0")
    locked_until = Column(DateTime, nullable=True)
    
    # Two-factor authentication
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(255), nullable=True)
    
    # DigiLocker integration
    digilocker_access_token = Column(Text, nullable=True)  # Encrypted
    digilocker_refresh_token = Column(Text, nullable=True)  # Encrypted
    digilocker_id = Column(String(100), nullable=True)
    digilocker_name = Column(String(255), nullable=True)
    digilocker_connected_at = Column(DateTime, nullable=True)
    digilocker_token_expires_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Soft delete
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    documents = relationship("Document", back_populates="user", lazy="dynamic")
    consent_logs = relationship("ConsentLog", back_populates="user", lazy="dynamic")
    
    def __repr__(self):
        return f"<User {self.email}>"
    
    def to_dict(self, exclude_sensitive: bool = True):
        """Convert user to dictionary"""
        data = {
            "id": str(self.id),
            "email": self.email,
            "phone_number": self.phone_number,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "two_factor_enabled": self.two_factor_enabled,
            "digilocker_connected": bool(self.digilocker_access_token),
            "digilocker_name": self.digilocker_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }
        if not exclude_sensitive:
            data["is_superuser"] = self.is_superuser
        return data
