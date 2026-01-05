"""
Authentication Router
Endpoints for user registration, login, and token management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import UserCreate, UserLogin, UserResponse, Token
from app.services.auth_service import AuthService
from app.models.consent_log import ConsentLog


router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user account
    
    - **email**: Valid email address
    - **password**: Strong password (8+ chars, uppercase, lowercase, digit, special char)
    - **phone_number**: Optional Indian phone number
    - **full_name**: Optional full name
    """
    auth_service = AuthService(db)
    
    try:
        user = await auth_service.create_user(user_data)
        
        # Log registration consent
        consent_log = ConsentLog(
            user_id=user.id,
            action="data_storage",  # Use lowercase string directly
            consent_given=True,
            consent_text="User agreed to terms and conditions during registration",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent")
        )
        db.add(consent_log)
        await db.commit()
        
        return user.to_dict()
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens
    
    - **email**: User email
    - **password**: User password
    
    Returns access token and refresh token
    """
    auth_service = AuthService(db)
    
    user, error = await auth_service.authenticate_user(login_data)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    tokens = await auth_service.create_tokens(user)
    
    return tokens


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token
    
    - **refresh_token**: Valid refresh token
    """
    auth_service = AuthService(db)
    
    tokens = await auth_service.refresh_tokens(refresh_token)
    
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return tokens


@router.post("/logout")
async def logout():
    """
    Logout user (client should discard tokens)
    
    Note: JWT tokens are stateless, so logout is handled client-side.
    For enhanced security, implement token blacklisting.
    """
    return {"message": "Successfully logged out. Please discard your tokens."}
