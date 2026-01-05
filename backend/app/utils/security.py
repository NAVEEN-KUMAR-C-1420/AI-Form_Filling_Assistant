"""
Security Utilities
Encryption, hashing, and security helper functions
"""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import bcrypt
from jose import jwt, JWTError
from loguru import logger

from app.config import settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception:
        return False


def get_encryption_key() -> bytes:
    """Generate encryption key from settings"""
    # Use PBKDF2 to derive a key from the encryption key setting
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=settings.SECRET_KEY[:16].encode(),
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.ENCRYPTION_KEY.encode()))
    return key


# Fernet cipher for symmetric encryption
_fernet = None


def get_fernet() -> Fernet:
    """Get Fernet cipher instance"""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_encryption_key())
    return _fernet


def encrypt_sensitive_data(data: str) -> str:
    """
    Encrypt sensitive data using Fernet (AES-128-CBC)
    Returns base64 encoded encrypted string
    """
    if not data:
        return ""
    try:
        fernet = get_fernet()
        encrypted = fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        raise ValueError("Failed to encrypt data")


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """
    Decrypt sensitive data
    Returns decrypted string
    """
    if not encrypted_data:
        return ""
    try:
        fernet = get_fernet()
        decoded = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted = fernet.decrypt(decoded)
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        raise ValueError("Failed to decrypt data")


# Aliases for encrypt/decrypt functions
def encrypt_value(data: str) -> str:
    """Alias for encrypt_sensitive_data"""
    return encrypt_sensitive_data(data)


def decrypt_value(encrypted_data: str) -> str:
    """Alias for decrypt_sensitive_data"""
    return decrypt_sensitive_data(encrypted_data)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate JWT token
    Returns payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Token decode error: {e}")
        return None


def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure random token"""
    return secrets.token_urlsafe(length)


def hash_file(file_content: bytes) -> str:
    """Generate SHA-256 hash of file content"""
    return hashlib.sha256(file_content).hexdigest()


def mask_sensitive_value(value: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive value, showing only last few characters
    Example: "1234567890" -> "XXXXXX7890"
    """
    if not value or len(value) <= visible_chars:
        return "X" * len(value) if value else ""
    
    masked_length = len(value) - visible_chars
    return "X" * masked_length + value[-visible_chars:]


def validate_aadhaar_checksum(aadhaar: str) -> bool:
    """
    Validate Aadhaar number using Verhoeff algorithm
    """
    # Verhoeff multiplication table
    d = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
        [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
        [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
        [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
        [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
        [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    ]
    
    # Permutation table
    p = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
        [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
        [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
        [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
        [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
    ]
    
    # Clean aadhaar number
    aadhaar = ''.join(filter(str.isdigit, aadhaar))
    
    if len(aadhaar) != 12:
        return False
    
    c = 0
    for i, digit in enumerate(reversed(aadhaar)):
        c = d[c][p[i % 8][int(digit)]]
    
    return c == 0


def validate_pan_format(pan: str) -> bool:
    """
    Validate PAN card format
    Format: AAAAA0000A (5 letters + 4 digits + 1 letter)
    """
    import re
    pan = pan.upper().strip()
    pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]$'
    return bool(re.match(pattern, pan))
