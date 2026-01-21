"""
File Utilities
File handling, validation, and processing helpers
"""
import os
import hashlib
import aiofiles
import uuid
from pathlib import Path
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException, status
from loguru import logger

from app.config import settings


ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.pdf'}
ALLOWED_MIME_TYPES = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/tiff': ['.tiff', '.tif'],
    'application/pdf': ['.pdf']
}


async def validate_file(file: UploadFile) -> Tuple[bool, str]:
    """
    Validate uploaded file
    Returns (is_valid, error_message)
    """
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_size:
        return False, f"File size exceeds maximum allowed ({settings.MAX_FILE_SIZE_MB}MB)"
    
    if file_size == 0:
        return False, "Empty file uploaded"
    
    # Check file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check MIME type
    content_type = file.content_type
    if content_type not in ALLOWED_MIME_TYPES:
        return False, f"Invalid content type: {content_type}"
    
    # Verify extension matches content type
    if ext not in ALLOWED_MIME_TYPES.get(content_type, []):
        return False, "File extension does not match content type"
    
    # Read magic bytes to verify file type
    magic_bytes = await read_magic_bytes(file)
    if not verify_magic_bytes(magic_bytes, ext):
        return False, "File content does not match declared type"
    
    return True, ""


async def read_magic_bytes(file: UploadFile, num_bytes: int = 8) -> bytes:
    """Read magic bytes from file"""
    content = await file.read(num_bytes)
    await file.seek(0)  # Reset file position
    return content


def verify_magic_bytes(magic: bytes, extension: str) -> bool:
    """Verify file magic bytes match extension"""
    magic_numbers = {
        '.jpg': [b'\xff\xd8\xff'],
        '.jpeg': [b'\xff\xd8\xff'],
        '.png': [b'\x89PNG'],
        '.tiff': [b'II*\x00', b'MM\x00*'],
        '.tif': [b'II*\x00', b'MM\x00*'],
        '.pdf': [b'%PDF']
    }
    
    expected = magic_numbers.get(extension, [])
    return any(magic.startswith(m) for m in expected)


async def save_temp_file(file: UploadFile, user_id: str) -> Tuple[str, str, int]:
    """
    Save uploaded file to temporary storage
    Returns (file_path, file_hash, file_size)
    """
    # Create user directory
    user_dir = Path(settings.TEMP_UPLOAD_DIR) / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    ext = Path(file.filename).suffix.lower()
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = user_dir / unique_filename
    
    # Read and hash content
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    file_size = len(content)
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    logger.info(f"Saved temp file: {file_path} ({file_size} bytes)")
    return str(file_path), file_hash, file_size


async def delete_temp_file(file_path: str) -> bool:
    """Delete temporary file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted temp file: {file_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting temp file {file_path}: {e}")
        return False


async def cleanup_user_temp_files(user_id: str) -> int:
    """
    Clean up all temporary files for a user
    Returns number of files deleted
    """
    user_dir = Path(settings.TEMP_UPLOAD_DIR) / user_id
    deleted_count = 0
    
    if user_dir.exists():
        for file_path in user_dir.iterdir():
            try:
                file_path.unlink()
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting {file_path}: {e}")
        
        # Remove user directory
        try:
            user_dir.rmdir()
        except Exception:
            pass
    
    logger.info(f"Cleaned up {deleted_count} temp files for user {user_id}")
    return deleted_count


def get_file_extension(filename: str) -> str:
    """Get file extension in lowercase"""
    return Path(filename).suffix.lower()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks"""
    # Remove path separators and null bytes
    sanitized = filename.replace('/', '').replace('\\', '').replace('\x00', '')
    # Get just the filename
    sanitized = Path(sanitized).name
    # Limit length
    if len(sanitized) > 255:
        ext = Path(sanitized).suffix
        sanitized = sanitized[:255-len(ext)] + ext
    return sanitized
