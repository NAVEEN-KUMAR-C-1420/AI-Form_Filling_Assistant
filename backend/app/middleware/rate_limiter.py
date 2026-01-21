"""
Rate Limiting Middleware
Prevents abuse by limiting request frequency
"""
import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token bucket rate limiting middleware
    Limits requests per IP address
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limit = settings.RATE_LIMIT_REQUESTS
        self.window = settings.RATE_LIMIT_WINDOW_SECONDS
        # Store: {ip: (tokens, last_update_time)}
        self.buckets: Dict[str, Tuple[float, float]] = defaultdict(
            lambda: (self.rate_limit, time.time())
        )
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Check rate limit
        allowed, remaining, reset_time = self._check_rate_limit(client_ip)
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": int(reset_time)
                },
                headers={
                    "X-RateLimit-Limit": str(self.rate_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_time)),
                    "Retry-After": str(int(reset_time))
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(int(remaining))
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check for forwarded headers (behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _check_rate_limit(self, client_ip: str) -> Tuple[bool, float, float]:
        """
        Check if request is allowed using token bucket algorithm
        Returns: (allowed, remaining_tokens, reset_time)
        """
        current_time = time.time()
        tokens, last_update = self.buckets[client_ip]
        
        # Calculate tokens to add based on time passed
        time_passed = current_time - last_update
        tokens_to_add = time_passed * (self.rate_limit / self.window)
        tokens = min(self.rate_limit, tokens + tokens_to_add)
        
        # Calculate reset time
        reset_time = current_time + self.window
        
        if tokens >= 1:
            # Allow request and consume token
            tokens -= 1
            self.buckets[client_ip] = (tokens, current_time)
            return True, tokens, reset_time
        else:
            # Deny request
            self.buckets[client_ip] = (tokens, current_time)
            return False, 0, reset_time
    
    def _cleanup_old_entries(self):
        """Remove old entries to prevent memory buildup"""
        current_time = time.time()
        cutoff = current_time - (self.window * 2)
        
        to_remove = [
            ip for ip, (_, last_update) in self.buckets.items()
            if last_update < cutoff
        ]
        
        for ip in to_remove:
            del self.buckets[ip]
