from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import logging

from shared.response import success_response, APIException
from modules.auth.router import get_current_user
from modules.auth.models import UserResponse
from .models import UserUpdate, AddressCreate, AddressUpdate, AddressResponse
from .manager import user_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/profile", response_model=dict)
async def get_profile(current_user: UserResponse = Depends(get_current_user)):
    """Get current user profile"""
    return success_response(
        data=current_user.dict(),
        message="Profile retrieved successfully"
    )

@router.put("/profile", response_model=dict)
async def update_profile(
    user_data: UserUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update user profile"""
    try:
        updated_user = await user_manager.update_user(current_user.id, user_data)
        return success_response(
            data=updated_user.dict(),
            message="Profile updated successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )

@router.delete("/profile", response_model=dict)
async def deactivate_account(current_user: UserResponse = Depends(get_current_user)):
    """Deactivate user account"""
    try:
        success = await user_manager.deactivate_user(current_user.id)
        return success_response(
            data={"deactivated": success},
            message="Account deactivated successfully"
        )
    except Exception as e:
        logger.error(f"Account deactivation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account deactivation failed"
        )

# Address endpoints
@router.post("/addresses", response_model=dict)
async def create_address(
    address_data: AddressCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create new address"""
    try:
        address = await user_manager.create_address(current_user.id, address_data)
        return success_response(
            data=address.dict(),
            message="Address created successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Address creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Address creation failed"
        )

@router.get("/addresses", response_model=dict)
async def get_addresses(current_user: UserResponse = Depends(get_current_user)):
    """Get user addresses"""
    try:
        addresses = await user_manager.get_user_addresses(current_user.id)
        return success_response(
            data=[addr.dict() for addr in addresses],
            message="Addresses retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Get addresses error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve addresses"
        )

@router.get("/addresses/{address_id}", response_model=dict)
async def get_address(
    address_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get specific address"""
    try:
        address = await user_manager.get_address_by_id(address_id)
        if not address or address.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found"
            )
        
        return success_response(
            data=address.dict(),
            message="Address retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get address error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve address"
        )

@router.put("/addresses/{address_id}", response_model=dict)
async def update_address(
    address_id: str,
    address_data: AddressUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update address"""
    try:
        address = await user_manager.update_address(address_id, current_user.id, address_data)
        return success_response(
            data=address.dict(),
            message="Address updated successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Address update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Address update failed"
        )

@router.delete("/addresses/{address_id}", response_model=dict)
async def delete_address(
    address_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete address"""
    try:
        success = await user_manager.delete_address(address_id, current_user.id)
        return success_response(
            data={"deleted": success},
            message="Address deleted successfully"
        )
    except Exception as e:
        logger.error(f"Address deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Address deletion failed"
        )