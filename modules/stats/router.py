from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
import logging

from shared.response import success_response, APIException
from modules.auth.router import get_current_user, get_current_user_optional
from modules.auth.models import UserResponse
from .models import DesignerStatsResponse
from .manager import stats_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("/designer", response_model=dict)
async def get_designer_stats(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get designer dashboard statistics"""
    try:
        stats = await stats_manager.get_designer_stats(current_user.id)
        return success_response(
            data=stats.dict(),
            message="Designer statistics retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting designer stats: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve designer statistics"
        )


@router.get("/orders", response_model=dict)
async def get_order_stats(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get order statistics"""
    try:
        stats = await stats_manager.get_order_stats(current_user.id)
        return success_response(
            data=stats.dict(),
            message="Order statistics retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting order stats: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve order statistics"
        )