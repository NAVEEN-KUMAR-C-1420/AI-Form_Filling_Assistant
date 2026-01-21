"""
DigiLocker Schemas
Pydantic models for DigiLocker API requests and responses
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DigiLockerAuthRequest(BaseModel):
    """Request to initiate DigiLocker OAuth"""
    redirect_url: Optional[str] = Field(
        None, 
        description="Custom redirect URL after auth (for extension)"
    )


class DigiLockerAuthResponse(BaseModel):
    """Response with DigiLocker authorization URL"""
    auth_url: str = Field(..., description="URL to redirect user for DigiLocker login")
    state: str = Field(..., description="State parameter for CSRF protection")


class DigiLockerCallbackRequest(BaseModel):
    """Callback data from DigiLocker OAuth"""
    code: str = Field(..., description="Authorization code from DigiLocker")
    state: str = Field(..., description="State parameter for verification")


class DigiLockerTokenResponse(BaseModel):
    """Token response after successful OAuth"""
    success: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    digilocker_id: Optional[str] = None
    name: Optional[str] = None
    error: Optional[str] = None


class DigiLockerDocument(BaseModel):
    """Document metadata from DigiLocker"""
    uri: str = Field(..., description="Unique document URI")
    name: str = Field(..., description="Document name")
    doc_type: str = Field(..., description="Our mapped document type")
    issuer: str = Field(..., description="Issuer organization ID")
    issuer_name: str = Field(..., description="Issuer name")
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    description: Optional[str] = None
    mime_type: str = "application/pdf"


class DigiLockerDocumentsResponse(BaseModel):
    """List of documents from DigiLocker"""
    success: bool
    documents: List[DigiLockerDocument] = []
    total: int = 0
    error: Optional[str] = None


class DigiLockerPullRequest(BaseModel):
    """Request to pull/download a document"""
    uri: str = Field(..., description="Document URI to pull")
    doc_type: Optional[str] = Field(None, description="Document type hint")


class DigiLockerEntity(BaseModel):
    """Extracted entity from DigiLocker document"""
    entity_type: str
    value: str
    confidence_score: float = 1.0
    extraction_method: str = "digilocker_api"
    original_language: str = "en"


class DigiLockerExtractedData(BaseModel):
    """Extracted data from a DigiLocker document"""
    success: bool
    doc_type: str
    source: str = "digilocker"
    entities: List[DigiLockerEntity] = []
    needs_ocr: bool = False
    error: Optional[str] = None


class DigiLockerConnectionStatus(BaseModel):
    """Status of user's DigiLocker connection"""
    connected: bool
    digilocker_id: Optional[str] = None
    name: Optional[str] = None
    connected_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class DigiLockerDisconnectResponse(BaseModel):
    """Response after disconnecting DigiLocker"""
    success: bool
    message: str


class DigiLockerImportRequest(BaseModel):
    """Request to import selected documents"""
    document_uris: List[str] = Field(..., description="List of document URIs to import")


class DigiLockerImportResponse(BaseModel):
    """Response after importing documents"""
    success: bool
    imported: int = 0
    failed: int = 0
    results: List[dict] = []
    error: Optional[str] = None
