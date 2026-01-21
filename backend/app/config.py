"""
Application Configuration
Manages all environment variables and settings
"""
import os
from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "AI Form Filling Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database - Using SQLite for local development (no PostgreSQL needed)
    DATABASE_URL: str = "sqlite+aiosqlite:///./form_assistant.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production-min-32-chars"
    ENCRYPTION_KEY: str = "your-32-byte-encryption-key-here"  # Must be 32 bytes for AES-256
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days in minutes
    REFRESH_TOKEN_EXPIRE_DAYS: int = 90  # 90 days for refresh token
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "*",
        "http://localhost:8000",
        "chrome-extension://*",
        "https://www.india.gov.in",
        "https://*.gov.in"
    ]
    
    # File Upload
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_FILE_TYPES: List[str] = ["image/jpeg", "image/png", "image/tiff", "application/pdf"]
    TEMP_UPLOAD_DIR: str = "./temp_uploads"
    
    # OCR Settings
    TESSERACT_CMD: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Windows path
    OCR_LANGUAGES: dict = {
        "english": "eng",
        "hindi": "hin",
        "tamil": "tam",
        "telugu": "tel",
        "kannada": "kan",
        "malayalam": "mal"
    }
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    
    # Audit Logging
    AUDIT_LOG_ENABLED: bool = True
    
    # DigiLocker Integration
    # Register at https://partners.digitallocker.gov.in/ to get credentials
    DIGILOCKER_CLIENT_ID: str = ""  # Your DigiLocker Partner Client ID
    DIGILOCKER_CLIENT_SECRET: str = ""  # Your DigiLocker Partner Client Secret
    DIGILOCKER_REDIRECT_URI: str = "http://localhost:8000/digilocker/auth/callback"
    DIGILOCKER_SANDBOX: bool = True  # Set to False for production
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
