import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from shared.db import db_manager
from shared.utils import (
    verify_password, get_password_hash, create_access_token, 
    create_refresh_token, verify_token, validate_email, 
    validate_password, generate_random_string, ACCESS_TOKEN_EXPIRE_MINUTES
)
from shared.response import NotFoundException, UnauthorizedException, ConflictException, ValidationException
from .models import UserLogin, UserRegister, UserResponse, TokenResponse

logger = logging.getLogger(__name__)

class AuthManager:
    """Authentication business logic manager"""
    
    async def register_user(self, user_data: UserRegister) -> UserResponse:
        """Register a new user"""
        try:
            # Validate email format
            if not validate_email(user_data.email):
                raise ValidationException(["Invalid email format"])
            
            # Validate password strength
            is_valid, password_errors = validate_password(user_data.password)
            if not is_valid:
                raise ValidationException(password_errors)
            
            # Check if user already exists
            existing_user = await db_manager.fetch_one(
                "SELECT id FROM users WHERE email = $1",
                user_data.email
            )
            
            if existing_user:
                raise ConflictException("User with this email already exists")
            
            # Hash password
            password_hash = get_password_hash(user_data.password)
            
            # Create user
            user_id = await db_manager.fetch_val(
                """
                INSERT INTO users (email, name, password_hash, role)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_data.email, user_data.name, password_hash, user_data.role
            )
            
            # Fetch created user
            user = await self.get_user_by_id(str(user_id))
            logger.info(f"User registered successfully: {user_data.email}")
            
            return user
            
        except Exception as e:
            logger.error(f"Failed to register user: {e}")
            raise
    
    async def authenticate_user(self, login_data: UserLogin) -> TokenResponse:
        """Authenticate user and return tokens"""
        try:
            # Get user by email
            user_data = await db_manager.fetch_one(
                """
                SELECT id, email, name, password_hash, avatar, role, 
                       is_active, email_verified, created_at, updated_at
                FROM users 
                WHERE email = $1 AND is_active = true
                """,
                login_data.email
            )
            
            if not user_data:
                raise UnauthorizedException("Invalid email or password")
            
            # Verify password
            if not verify_password(login_data.password, user_data["password_hash"]):
                raise UnauthorizedException("Invalid email or password")
            
            # Create tokens
            token_data = {"sub": str(user_data["id"]), "email": user_data["email"]}
            access_token = create_access_token(token_data)
            refresh_token = create_refresh_token(token_data)
            
            # Store refresh token in database
            await self._store_refresh_token(str(user_data["id"]), refresh_token)
            
            # Create user response
            user = UserResponse(
                id=str(user_data["id"]),
                email=user_data["email"],
                name=user_data["name"],
                avatar=user_data["avatar"],
                role=user_data["role"],
                is_active=user_data["is_active"],
                email_verified=user_data["email_verified"],
                created_at=user_data["created_at"],
                updated_at=user_data["updated_at"]
            )
            
            logger.info(f"User authenticated successfully: {login_data.email}")
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=user
            )
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
    
    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token"""
        try:
            # Verify refresh token
            payload = verify_token(refresh_token)
            if not payload or payload.get("type") != "refresh":
                raise UnauthorizedException("Invalid refresh token")
            
            user_id = payload.get("sub")
            if not user_id:
                raise UnauthorizedException("Invalid refresh token")
            
            # Check if refresh token exists in database
            token_exists = await db_manager.fetch_one(
                """
                SELECT id FROM user_sessions 
                WHERE user_id = $1 AND token_jti = $2 AND is_revoked = false
                AND expires_at > CURRENT_TIMESTAMP
                """,
                user_id, payload.get("jti")
            )
            
            if not token_exists:
                raise UnauthorizedException("Refresh token has been revoked or expired")
            
            # Get user data
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UnauthorizedException("User not found")
            
            # Create new tokens
            token_data = {"sub": user_id, "email": user.email}
            new_access_token = create_access_token(token_data)
            new_refresh_token = create_refresh_token(token_data)
            
            # Revoke old refresh token and store new one
            await self._revoke_refresh_token(payload.get("jti"))
            await self._store_refresh_token(user_id, new_refresh_token)
            
            return TokenResponse(
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=user
            )
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise
    
    async def logout_user(self, refresh_token: str) -> bool:
        """Logout user by revoking refresh token"""
        try:
            payload = verify_token(refresh_token)
            if payload and payload.get("jti"):
                await self._revoke_refresh_token(payload.get("jti"))
            return True
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """Get user by ID"""
        try:
            user_data = await db_manager.fetch_one(
                """
                SELECT id, email, name, avatar, role, is_active, 
                       email_verified, created_at, updated_at
                FROM users 
                WHERE id = $1 AND is_active = true
                """,
                user_id
            )
            
            if not user_data:
                return None
            
            return UserResponse(
                id=str(user_data["id"]),
                email=user_data["email"],
                name=user_data["name"],
                avatar=user_data["avatar"],
                role=user_data["role"],
                is_active=user_data["is_active"],
                email_verified=user_data["email_verified"],
                created_at=user_data["created_at"],
                updated_at=user_data["updated_at"]
            )
            
        except Exception as e:
            logger.error(f"Failed to get user by ID: {e}")
            return None
    
    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """Change user password"""
        try:
            # Get current password hash
            current_hash = await db_manager.fetch_val(
                "SELECT password_hash FROM users WHERE id = $1",
                user_id
            )
            
            if not current_hash:
                raise NotFoundException("User")
            
            # Verify current password
            if not verify_password(current_password, current_hash):
                raise UnauthorizedException("Current password is incorrect")
            
            # Validate new password
            is_valid, password_errors = validate_password(new_password)
            if not is_valid:
                raise ValidationException(password_errors)
            
            # Hash new password
            new_hash = get_password_hash(new_password)
            
            # Update password
            await db_manager.execute_query(
                "UPDATE users SET password_hash = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                new_hash, user_id
            )
            
            # Revoke all refresh tokens for this user
            await db_manager.execute_query(
                "UPDATE user_sessions SET is_revoked = true WHERE user_id = $1",
                user_id
            )
            
            logger.info(f"Password changed successfully for user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to change password: {e}")
            raise
    
    async def _store_refresh_token(self, user_id: str, refresh_token: str) -> None:
        """Store refresh token in database"""
        payload = verify_token(refresh_token)
        if payload:
            await db_manager.execute_query(
                """
                INSERT INTO user_sessions (user_id, token_jti, expires_at)
                VALUES ($1, $2, $3)
                """,
                user_id, payload.get("jti"), 
                datetime.fromtimestamp(payload.get("exp"))
            )
    
    async def _revoke_refresh_token(self, jti: str) -> None:
        """Revoke refresh token"""
        await db_manager.execute_query(
            "UPDATE user_sessions SET is_revoked = true WHERE token_jti = $1",
            jti
        )

# Global auth manager instance
auth_manager = AuthManager()