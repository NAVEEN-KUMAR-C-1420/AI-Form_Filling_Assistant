"""
Application Configuration
Manages all environment variables and settings
"""
from typing import List, Literal
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_parse_delimiter=",",
    )
    
    # Application
    APP_NAME: str = "AI Form Filling Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./form_assistant.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    AUTO_CREATE_TABLES: bool = True
    
    # Security
    SECRET_KEY: str = ""
    ENCRYPTION_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days in minutes
    REFRESH_TOKEN_EXPIRE_DAYS: int = 90  # 90 days for refresh token
    ENABLE_HTTPS_REDIRECT: bool = True
    ENABLE_SECURITY_HEADERS: bool = True
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "*.localhost"]
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://localhost:3000",
        "chrome-extension://*"
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

    @field_validator("ALLOWED_ORIGINS", "ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_csv_list(cls, value):
        """Allow comma-separated values for list settings from env vars."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_settings(self):
        """Fail fast on insecure production configuration."""
        if self.ENVIRONMENT != "production":
            return self

        if self.DEBUG:
            raise ValueError("DEBUG must be false in production")

        if len(self.SECRET_KEY.strip()) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")

        if len(self.ENCRYPTION_KEY.strip()) < 16:
            raise ValueError("ENCRYPTION_KEY must be set in production")

        if "*" in self.ALLOWED_ORIGINS:
            raise ValueError("ALLOWED_ORIGINS cannot contain '*' in production")

        if not self.ALLOWED_HOSTS:
            raise ValueError("ALLOWED_HOSTS must be configured in production")

        return self


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
