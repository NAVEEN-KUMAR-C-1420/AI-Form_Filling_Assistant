"""
Authentication Schemas
Pydantic models for auth requests and responses
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
import re


class UserCreate(BaseModel):
    """Schema for user registration"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    phone_number: Optional[str] = Field(None, description="Indian phone number")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")
    
    @validator("password")
    def validate_password(cls, v):
        """Validate password strength"""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v
    
    @validator("phone_number")
    def validate_phone(cls, v):
        """Validate Indian phone number"""
        if v:
            # Remove spaces and dashes
            cleaned = re.sub(r"[\s\-]", "", v)
            # Check for valid Indian number format
            if not re.match(r"^(\+91)?[6-9]\d{9}$", cleaned):
                raise ValueError("Invalid Indian phone number format")
            return cleaned
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
                "phone_number": "+919876543210",
                "full_name": "Raj Kumar"
            }
        }


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!"
            }
        }


class UserResponse(BaseModel):
    """Schema for user response"""
    id: str
    email: str
    phone_number: Optional[str]
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    two_factor_enabled: bool
    created_at: Optional[datetime]
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }


class TokenData(BaseModel):
    """Schema for decoded token data"""
    user_id: str
    email: str
    token_type: str  # access or refresh


class PasswordReset(BaseModel):
    """Schema for password reset"""
    email: EmailStr = Field(..., description="User email address")


class PasswordResetConfirm(BaseModel):
    """Schema for confirming password reset"""
    token: str = Field(..., description="Reset token")
    new_password: str = Field(..., min_length=8, max_length=128)
    
    @validator("new_password")
    def validate_password(cls, v):
        """Validate password strength"""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v
