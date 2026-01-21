"""
Audit Logging Middleware
Logs all API requests for security audit trail
"""
import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from app.config import settings


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all API requests for audit purposes
    """
    
    # Paths to exclude from detailed logging
    EXCLUDE_PATHS = {"/health", "/", "/docs", "/redoc", "/openapi.json"}
    
    # Sensitive paths that need extra logging
    SENSITIVE_PATHS = {
        "/auth/login", "/auth/register",
        "/documents/upload", "/documents/confirm",
        "/user/data"
    }
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Store in request state
        request.state.request_id = request_id
        
        # Skip detailed logging for excluded paths
        if request.url.path in self.EXCLUDE_PATHS:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        
        # Capture request details
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        
        # Log request
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
            "user_agent": request.headers.get("User-Agent", "Unknown")[:200]
        }
        
        # Add user ID if authenticated
        auth_header = request.headers.get("Authorization")
        if auth_header:
            log_data["has_auth"] = True
        
        if settings.AUDIT_LOG_ENABLED:
            logger.info(f"API Request: {log_data}")
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log response
            response_log = {
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": duration_ms
            }
            
            # Log sensitive path access
            if request.url.path in self.SENSITIVE_PATHS:
                logger.info(f"Sensitive API Access: {response_log}")
            elif settings.AUDIT_LOG_ENABLED:
                logger.debug(f"API Response: {response_log}")
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms}ms"
            
            return response
            
        except Exception as e:
            # Log error
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"API Error: request_id={request_id} path={request.url.path} "
                f"error={str(e)} duration_ms={duration_ms}"
            )
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
