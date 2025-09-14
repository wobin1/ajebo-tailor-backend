from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging

from shared.response import success_response, APIException
from shared.utils import verify_token
from .models import (
    UserLogin, UserRegister, UserResponse, TokenResponse, 
    RefreshTokenRequest, ChangePasswordRequest
)
from .manager import auth_manager

logger = logging.getLogger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Dependency to get current user from JWT token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserResponse:
    """Get current authenticated user"""
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = await auth_manager.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except APIException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Optional authentication dependency
async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))) -> Optional[UserResponse]:
    """Get current user if authenticated, otherwise None"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

@router.post("/register", response_model=dict)
async def register(user_data: UserRegister):
    """Register a new user"""
    try:
        user = await auth_manager.register_user(user_data)
        return success_response(
            data=user.dict(),
            message="User registered successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=dict)
async def login(login_data: UserLogin):
    """Authenticate user and return tokens"""
    try:
        token_response = await auth_manager.authenticate_user(login_data)
        return success_response(
            data=token_response.dict(),
            message="Login successful"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/refresh", response_model=dict)
async def refresh_token(refresh_data: RefreshTokenRequest):
    """Refresh access token"""
    try:
        token_response = await auth_manager.refresh_access_token(refresh_data.refresh_token)
        return success_response(
            data=token_response.dict(),
            message="Token refreshed successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@router.post("/logout", response_model=dict)
async def logout(refresh_data: RefreshTokenRequest):
    """Logout user by revoking refresh token"""
    try:
        success = await auth_manager.logout_user(refresh_data.refresh_token)
        return success_response(
            data={"logged_out": success},
            message="Logout successful"
        )
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return success_response(
            data={"logged_out": True},
            message="Logout successful"
        )

@router.get("/me", response_model=dict)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    """Get current user information"""
    return success_response(
        data=current_user.dict(),
        message="User information retrieved successfully"
    )

@router.post("/change-password", response_model=dict)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """Change user password"""
    try:
        success = await auth_manager.change_password(
            current_user.id,
            password_data.current_password,
            password_data.new_password
        )
        return success_response(
            data={"password_changed": success},
            message="Password changed successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )