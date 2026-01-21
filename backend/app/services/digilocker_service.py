"""
DigiLocker Integration Service
Handles OAuth2 authentication and document fetching from DigiLocker
DigiLocker API Documentation: https://partners.digitallocker.gov.in/
"""
import httpx
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
from loguru import logger

from app.config import settings


class DigiLockerService:
    """Service for DigiLocker API integration"""
    
    # DigiLocker API endpoints (Sandbox - change to production in .env)
    BASE_URL = "https://digilocker.meripehchaan.gov.in"
    SANDBOX_URL = "https://digilocker.meripehchaan.gov.in"  # Sandbox for testing
    
    # OAuth2 endpoints
    AUTHORIZE_URL = "/public/oauth2/1/authorize"
    TOKEN_URL = "/public/oauth2/2/token"
    
    # Document endpoints
    ISSUED_DOCS_URL = "/public/oauth2/1/files/issued"
    PULL_DOC_URL = "/public/oauth2/3/files/issued"
    AADHAAR_URL = "/public/oauth2/1/xml/eaadhaar"
    
    # Document type mappings (URI to our document types)
    DOC_TYPE_MAPPING = {
        "ADHAR": "aadhaar",
        "PANCR": "pan",
        "DRVLC": "driving_license",
        "VOTERID": "voter_id",
        "INCMC": "income_certificate",
        "COMMC": "community_certificate",
    }
    
    # Issuer Organization IDs (common issuers)
    ISSUERS = {
        "aadhaar": "in.gov.uidai",
        "pan": "in.gov.cbdt-nsdlpan",
        "driving_license": "in.gov.transport.dl",
        "voter_id": "in.gov.eci",
    }
    
    def __init__(self):
        self.client_id = settings.DIGILOCKER_CLIENT_ID
        self.client_secret = settings.DIGILOCKER_CLIENT_SECRET
        self.redirect_uri = settings.DIGILOCKER_REDIRECT_URI
        self.base_url = self.SANDBOX_URL if settings.DIGILOCKER_SANDBOX else self.BASE_URL
    
    def generate_code_verifier(self) -> str:
        """Generate PKCE code verifier"""
        return secrets.token_urlsafe(64)[:128]
    
    def generate_code_challenge(self, verifier: str) -> str:
        """Generate PKCE code challenge from verifier"""
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    
    def get_authorization_url(self, state: str, code_verifier: str) -> Dict[str, str]:
        """
        Generate DigiLocker authorization URL for OAuth2 flow
        
        Args:
            state: Random state parameter for CSRF protection
            code_verifier: PKCE code verifier
            
        Returns:
            Dict with auth_url, state, and code_verifier
        """
        code_challenge = self.generate_code_challenge(code_verifier)
        
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            # Scopes for accessing documents
            "scope": "openid profile address email picture aadhaar pan issued_docs",
        }
        
        auth_url = f"{self.base_url}{self.AUTHORIZE_URL}?{urlencode(params)}"
        
        return {
            "auth_url": auth_url,
            "state": state,
            "code_verifier": code_verifier
        }
    
    async def exchange_code_for_token(
        self, 
        code: str, 
        code_verifier: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token
        
        Args:
            code: Authorization code from callback
            code_verifier: PKCE code verifier used in authorization
            
        Returns:
            Token response with access_token, refresh_token, etc.
        """
        token_url = f"{self.base_url}{self.TOKEN_URL}"
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code_verifier": code_verifier,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    token_url,
                    data=data,
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    logger.info("DigiLocker token exchange successful")
                    return {
                        "success": True,
                        "access_token": token_data.get("access_token"),
                        "refresh_token": token_data.get("refresh_token"),
                        "token_type": token_data.get("token_type", "Bearer"),
                        "expires_in": token_data.get("expires_in", 3600),
                        "digilocker_id": token_data.get("digilocker_id"),
                        "name": token_data.get("name"),
                        "dob": token_data.get("dob"),
                        "gender": token_data.get("gender"),
                        "eaadhaar": token_data.get("eaadhaar"),
                    }
                else:
                    logger.error(f"DigiLocker token exchange failed: {response.text}")
                    return {
                        "success": False,
                        "error": response.json().get("error_description", "Token exchange failed")
                    }
                    
            except Exception as e:
                logger.exception(f"DigiLocker token exchange error: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh expired access token"""
        token_url = f"{self.base_url}{self.TOKEN_URL}"
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    token_url,
                    data=data,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    return {"success": True, **response.json()}
                else:
                    return {"success": False, "error": "Token refresh failed"}
                    
            except Exception as e:
                logger.exception(f"Token refresh error: {e}")
                return {"success": False, "error": str(e)}
    
    async def get_issued_documents(self, access_token: str) -> Dict[str, Any]:
        """
        Fetch list of documents issued to user in DigiLocker
        
        Args:
            access_token: Valid DigiLocker access token
            
        Returns:
            List of issued documents with metadata
        """
        url = f"{self.base_url}{self.ISSUED_DOCS_URL}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=30.0)
                
                if response.status_code == 200:
                    data = response.json()
                    documents = data.get("items", [])
                    
                    # Process and categorize documents
                    processed_docs = []
                    for doc in documents:
                        doc_info = self._process_document_info(doc)
                        if doc_info:
                            processed_docs.append(doc_info)
                    
                    logger.info(f"Fetched {len(processed_docs)} documents from DigiLocker")
                    return {
                        "success": True,
                        "documents": processed_docs,
                        "total": len(processed_docs)
                    }
                else:
                    logger.error(f"Failed to fetch documents: {response.text}")
                    return {
                        "success": False,
                        "error": "Failed to fetch documents",
                        "documents": []
                    }
                    
            except Exception as e:
                logger.exception(f"Error fetching documents: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "documents": []
                }
    
    def _process_document_info(self, doc: Dict) -> Optional[Dict]:
        """Process raw document info from DigiLocker"""
        uri = doc.get("uri", "")
        doc_type = doc.get("doctype", "")
        
        # Map to our document types
        our_type = None
        for dl_type, our_doc_type in self.DOC_TYPE_MAPPING.items():
            if dl_type in doc_type.upper() or dl_type in uri.upper():
                our_type = our_doc_type
                break
        
        if not our_type:
            our_type = "other"
        
        return {
            "uri": uri,
            "name": doc.get("name", "Unknown Document"),
            "doc_type": our_type,
            "issuer": doc.get("issuerid", ""),
            "issuer_name": doc.get("issuername", ""),
            "issue_date": doc.get("issuedate", ""),
            "expiry_date": doc.get("expirydate", ""),
            "description": doc.get("description", ""),
            "size": doc.get("size", 0),
            "mime_type": doc.get("mime", "application/pdf"),
        }
    
    async def pull_document(
        self, 
        access_token: str, 
        uri: str,
        doc_type: str = None
    ) -> Dict[str, Any]:
        """
        Pull/download a specific document from DigiLocker
        
        Args:
            access_token: Valid access token
            uri: Document URI from issued documents list
            doc_type: Optional document type hint
            
        Returns:
            Document data with extracted information
        """
        url = f"{self.base_url}{self.PULL_DOC_URL}/{uri}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/xml, application/pdf, image/*",
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=60.0)
                
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    
                    # For XML documents (like eAadhaar), parse directly
                    if "xml" in content_type:
                        return await self._parse_xml_document(response.text, doc_type)
                    
                    # For PDF/images, return as base64 for further OCR processing
                    return {
                        "success": True,
                        "content_type": content_type,
                        "data": base64.b64encode(response.content).decode(),
                        "doc_type": doc_type,
                        "needs_ocr": True
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to pull document: {response.status_code}"
                    }
                    
            except Exception as e:
                logger.exception(f"Error pulling document: {e}")
                return {"success": False, "error": str(e)}
    
    async def get_eaadhaar(self, access_token: str) -> Dict[str, Any]:
        """
        Fetch eAadhaar XML directly (if consent given)
        This provides structured data without OCR
        """
        url = f"{self.base_url}{self.AADHAAR_URL}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/xml",
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=30.0)
                
                if response.status_code == 200:
                    return await self._parse_aadhaar_xml(response.text)
                else:
                    return {
                        "success": False,
                        "error": "Failed to fetch eAadhaar"
                    }
                    
            except Exception as e:
                logger.exception(f"Error fetching eAadhaar: {e}")
                return {"success": False, "error": str(e)}
    
    async def _parse_xml_document(self, xml_content: str, doc_type: str) -> Dict[str, Any]:
        """Parse XML document content based on type"""
        import xml.etree.ElementTree as ET
        
        try:
            root = ET.fromstring(xml_content)
            
            if doc_type == "aadhaar":
                return await self._parse_aadhaar_xml(xml_content)
            
            # Generic XML parsing
            data = {}
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    data[elem.tag] = elem.text.strip()
                for attr, value in elem.attrib.items():
                    data[f"{elem.tag}_{attr}"] = value
            
            return {
                "success": True,
                "data": data,
                "doc_type": doc_type,
                "needs_ocr": False
            }
            
        except Exception as e:
            logger.error(f"XML parsing error: {e}")
            return {"success": False, "error": "Failed to parse XML"}
    
    async def _parse_aadhaar_xml(self, xml_content: str) -> Dict[str, Any]:
        """Parse eAadhaar XML format"""
        import xml.etree.ElementTree as ET
        
        try:
            root = ET.fromstring(xml_content)
            
            # eAadhaar XML has structured format
            # Root element is typically 'OfflinePaperlessKyc' or 'PrintLetterBarcodeData'
            
            poi = root.find(".//Poi") or root  # Proof of Identity
            poa = root.find(".//Poa")  # Proof of Address
            
            # Extract attributes
            data = {
                "full_name": poi.get("name", ""),
                "date_of_birth": poi.get("dob", ""),
                "gender": poi.get("gender", ""),
                "aadhaar_number": self._mask_aadhaar(root.get("uid", "") or poi.get("uid", "")),
            }
            
            # Address from Poa
            if poa is not None:
                address_parts = []
                for field in ["house", "street", "lm", "loc", "vtc", "subdist", "dist", "state", "pc"]:
                    value = poa.get(field, "")
                    if value:
                        address_parts.append(value)
                data["address"] = ", ".join(address_parts)
                data["pincode"] = poa.get("pc", "")
            
            # Format date of birth with month name
            if data["date_of_birth"]:
                data["date_of_birth"] = self._format_date(data["date_of_birth"])
            
            return {
                "success": True,
                "doc_type": "aadhaar",
                "data": data,
                "entities": self._convert_to_entities(data, "aadhaar"),
                "needs_ocr": False,
                "source": "digilocker_xml"
            }
            
        except Exception as e:
            logger.exception(f"Error parsing Aadhaar XML: {e}")
            return {"success": False, "error": "Failed to parse Aadhaar XML"}
    
    def _mask_aadhaar(self, aadhaar: str) -> str:
        """Return Aadhaar in display format (XXXX XXXX 1234)"""
        clean = aadhaar.replace(" ", "").replace("-", "")
        if len(clean) == 12:
            return f"{clean[:4]} {clean[4:8]} {clean[8:]}"
        return aadhaar
    
    def _format_date(self, date_str: str) -> str:
        """Convert date to 'DD Mon YYYY' format"""
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Try different formats
        for fmt in ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return f"{dt.day} {month_names[dt.month-1]} {dt.year}"
            except ValueError:
                continue
        
        return date_str
    
    def _convert_to_entities(self, data: Dict, doc_type: str) -> List[Dict]:
        """Convert parsed data to entity format for storage"""
        entities = []
        
        entity_mapping = {
            "full_name": "full_name",
            "date_of_birth": "date_of_birth",
            "gender": "gender",
            "address": "address",
            "aadhaar_number": "aadhaar_number",
            "pan_number": "pan_number",
            "driving_license_number": "driving_license_number",
            "voter_id_number": "voter_id_number",
            "father_name": "father_name",
            "blood_group": "blood_group",
            "validity_date": "validity_date",
            "issue_date": "issue_date",
        }
        
        for key, value in data.items():
            if value and key in entity_mapping:
                entities.append({
                    "entity_type": entity_mapping[key],
                    "value": value,
                    "confidence_score": 1.0,  # High confidence from structured data
                    "extraction_method": "digilocker_api",
                    "original_language": "en"
                })
        
        return entities


# Singleton instance
digilocker_service = DigiLockerService()
