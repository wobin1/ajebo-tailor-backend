from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime
import logging

from shared.auth import get_current_user, require_admin
from shared.response import success_response, error_response
from shared.utils import PaginationParams
from modules.orders.models import OrderUpdate, OrderFilters, OrderStatus, PaymentStatus, PaymentMethod, OrderPriority
from .order_manager import AdminOrderManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["Admin Orders"])
order_manager = AdminOrderManager()

@router.get("/")
async def get_orders(
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    
    # Filters
    status: Optional[OrderStatus] = Query(None, description="Filter by order status"),
    payment_status: Optional[PaymentStatus] = Query(None, description="Filter by payment status"),
    payment_method: Optional[PaymentMethod] = Query(None, description="Filter by payment method"),
    priority: Optional[OrderPriority] = Query(None, description="Filter by priority"),
    date_from: Optional[datetime] = Query(None, description="Filter orders from date"),
    date_to: Optional[datetime] = Query(None, description="Filter orders to date"),
    min_amount: Optional[float] = Query(None, description="Minimum order amount"),
    max_amount: Optional[float] = Query(None, description="Maximum order amount"),
    search: Optional[str] = Query(None, description="Search in order number, customer name, email"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    
    current_user = Depends(require_admin)
):
    """Get all orders with filtering and pagination (admin only)"""
    logger.info(f"Admin orders endpoint called by user {current_user.id}")
    logger.info(f"Request params - page: {page}, limit: {limit}, status: {status}, search: {search}")
    try:
        # Create filters object
        filters = OrderFilters(
            status=status,
            payment_status=payment_status,
            payment_method=payment_method,
            priority=priority,
            date_from=date_from,
            date_to=date_to,
            min_amount=min_amount,
            max_amount=max_amount,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Create pagination object
        pagination = PaginationParams(page=page, limit=limit)
        
        logger.info("Calling order_manager.get_orders with filters and pagination")
        result = await order_manager.get_orders(filters, pagination)
        
        logger.info(f"Retrieved {len(result['orders'])} orders out of {result['total']} total")
        logger.info(f"Sample order data: {result['orders'][0] if result['orders'] else 'No orders found'}")
        
        return success_response(
            data=result["orders"],
            message="Orders retrieved successfully",
            meta={
                "pagination": {
                    "current_page": result["page"],
                    "per_page": result["limit"],
                    "total": result["total"],
                    "total_pages": result["total_pages"]
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error in get_orders endpoint: {str(e)}", exc_info=True)
        return error_response(str(e), 500)

@router.get("/{order_id}")
async def get_order(
    order_id: str,
    current_user = Depends(require_admin)
):
    """Get a specific order by ID (admin only)"""
    try:
        order = await order_manager.get_order_by_id(order_id)
        
        if not order:
            return error_response("Order not found", 404)
        
        return success_response(
            data=order,
            message="Order retrieved successfully"
        )
        
    except Exception as e:
        return error_response(str(e), 500)

@router.put("/{order_id}")
async def update_order(
    order_id: str,
    order_data: OrderUpdate,
    current_user = Depends(require_admin)
):
    """Update an order (admin only)"""
    try:
        updated_order = await order_manager.update_order(order_id, order_data)
        
        return success_response(
            data=updated_order,
            message="Order updated successfully"
        )
        
    except Exception as e:
        return error_response(str(e), 500)

@router.delete("/{order_id}")
async def delete_order(
    order_id: str,
    current_user = Depends(require_admin)
):
    """Delete/Cancel an order (admin only)"""
    try:
        success = await order_manager.delete_order(order_id)
        
        if success:
            return success_response(
                data={"deleted": True},
                message="Order cancelled successfully"
            )
        else:
            return error_response("Failed to cancel order", 500)
        
    except Exception as e:
        return error_response(str(e), 500)

@router.get("/statistics/overview")
async def get_order_statistics(
    current_user = Depends(require_admin)
):
    """Get order statistics for admin dashboard"""
    try:
        stats = await order_manager.get_order_statistics()
        
        return success_response(
            data=stats,
            message="Order statistics retrieved successfully"
        )
        
    except Exception as e:
        return error_response(str(e), 500)



