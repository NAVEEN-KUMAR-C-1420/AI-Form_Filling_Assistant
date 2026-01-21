"""
Authentication Service
Business logic for user authentication and authorization
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from loguru import logger

from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin, Token
from app.utils.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token
)
from app.config import settings


class AuthService:
    """Authentication service for user management"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_user(self, user_data: UserCreate) -> User:
        """
        Create a new user account
        """
        # Check if email exists
        existing = await self._get_user_by_email(user_data.email)
        if existing:
            raise ValueError("Email already registered")
        
        # Check if phone exists
        if user_data.phone_number:
            existing_phone = await self._get_user_by_phone(user_data.phone_number)
            if existing_phone:
                raise ValueError("Phone number already registered")
        
        # Create user
        user = User(
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            phone_number=user_data.phone_number,
            full_name=user_data.full_name,
            is_active=True,
            is_verified=False
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"Created new user: {user.email}")
        return user
    
    async def authenticate_user(self, login_data: UserLogin) -> Tuple[Optional[User], str]:
        """
        Authenticate user with email and password
        Returns (user, error_message)
        """
        user = await self._get_user_by_email(login_data.email)
        
        if not user:
            return None, "Invalid email or password"
        
        if not user.is_active:
            return None, "Account is deactivated"
        
        if user.is_deleted:
            return None, "Account has been deleted"
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            return None, f"Account locked until {user.locked_until.isoformat()}"
        
        # Verify password
        if not verify_password(login_data.password, user.hashed_password):
            await self._handle_failed_login(user)
            return None, "Invalid email or password"
        
        # Reset failed attempts on successful login
        await self._reset_failed_attempts(user)
        await self._update_last_login(user)
        
        logger.info(f"User authenticated: {user.email}")
        return user, ""
    
    async def create_tokens(self, user: User) -> Token:
        """Create access and refresh tokens for user"""
        token_data = {
            "sub": str(user.id),
            "email": user.email
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    async def refresh_tokens(self, refresh_token: str) -> Optional[Token]:
        """Refresh access token using refresh token"""
        payload = decode_token(refresh_token)
        
        if not payload:
            return None
        
        if payload.get("type") != "refresh":
            return None
        
        user_id = payload.get("sub")
        user = await self.get_user_by_id(UUID(user_id))
        
        if not user or not user.is_active:
            return None
        
        return await self.create_tokens(user)
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.is_deleted == False)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        result = await self.db.execute(
            select(User).where(User.email == email, User.is_deleted == False)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_phone(self, phone: str) -> Optional[User]:
        """Get user by phone number"""
        result = await self.db.execute(
            select(User).where(User.phone_number == phone, User.is_deleted == False)
        )
        return result.scalar_one_or_none()
    
    async def _handle_failed_login(self, user: User):
        """Handle failed login attempt"""
        attempts = int(user.failed_login_attempts or "0") + 1
        
        update_data = {"failed_login_attempts": str(attempts)}
        
        # Lock account after 5 failed attempts
        if attempts >= 5:
            update_data["locked_until"] = datetime.utcnow() + timedelta(minutes=30)
            logger.warning(f"Account locked due to failed attempts: {user.email}")
        
        await self.db.execute(
            update(User).where(User.id == user.id).values(**update_data)
        )
        await self.db.commit()
    
    async def _reset_failed_attempts(self, user: User):
        """Reset failed login attempts"""
        await self.db.execute(
            update(User).where(User.id == user.id).values(
                failed_login_attempts="0",
                locked_until=None
            )
        )
        await self.db.commit()
    
    async def _update_last_login(self, user: User):
        """Update last login timestamp"""
        await self.db.execute(
            update(User).where(User.id == user.id).values(
                last_login=datetime.utcnow()
            )
        )
        await self.db.commit()
    
    async def deactivate_user(self, user_id: UUID) -> bool:
        """Deactivate user account (soft delete)"""
        result = await self.db.execute(
            update(User).where(User.id == user_id).values(
                is_deleted=True,
                deleted_at=datetime.utcnow(),
                is_active=False
            )
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def change_password(
        self, user_id: UUID, old_password: str, new_password: str
    ) -> Tuple[bool, str]:
        """Change user password"""
        user = await self.get_user_by_id(user_id)
        
        if not user:
            return False, "User not found"
        
        if not verify_password(old_password, user.hashed_password):
            return False, "Current password is incorrect"
        
        await self.db.execute(
            update(User).where(User.id == user_id).values(
                hashed_password=hash_password(new_password),
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()
        
        logger.info(f"Password changed for user: {user.email}")
        return True, "Password changed successfully"
