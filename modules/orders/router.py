from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from datetime import datetime
import logging

from shared.response import success_response, paginated_response, APIException
from shared.utils import PaginationParams
from shared.db import db_manager
from modules.auth.router import get_current_user, get_current_user_optional
from modules.auth.models import UserResponse
from .models import (
    OrderCreate, DesignerOrderCreate, OrderUpdate, OrderResponse, OrderSummary, CartSummary, CartItemCreate,
    OrderFilters, OrderStatus, PaymentStatus, PaymentMethod
)
from .manager import order_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("")
async def create_order(
    order_data: OrderCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new order"""
    try:
        order = await order_manager.create_order(current_user.id, order_data)
        return success_response(
            data={"id": order},
            message="Order created successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Create order error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Order creation failed"
        )

@router.post("/designer")
async def create_designer_order(
    order_data: DesignerOrderCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new designer order (no shipping address required)"""
    # Check if user has designer permissions
    if current_user.role not in ["admin", "designer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Designer role required."
        )
    
    try:
        # Convert DesignerOrderCreate to OrderCreate with default values
        regular_order_data = OrderCreate(
            items=order_data.items,
            shipping_address_id=None,  # Designer orders don't require shipping address
            billing_address_id=None,
            payment_method=order_data.payment_method,
            notes=order_data.notes
        )
        
        order = await order_manager.create_order(current_user.id, regular_order_data)
        return success_response(
            data={"id": order},
            message="Designer order created successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Create designer order error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Designer order creation failed"
        )

@router.get("", response_model=dict)
async def get_user_orders(
    # Filtering parameters
    status_filter: Optional[OrderStatus] = Query(None, alias="status", description="Filter by order status"),
    payment_status: Optional[PaymentStatus] = Query(None, description="Filter by payment status"),
    payment_method: Optional[PaymentMethod] = Query(None, description="Filter by payment method"),
    date_from: Optional[datetime] = Query(None, description="Filter orders from date"),
    date_to: Optional[datetime] = Query(None, description="Filter orders to date"),
    min_amount: Optional[float] = Query(None, ge=0, description="Minimum order amount"),
    max_amount: Optional[float] = Query(None, ge=0, description="Maximum order amount"),
    search: Optional[str] = Query(None, description="Search in order number"),
    sort_by: Optional[str] = Query("created_at", pattern="^(created_at|updated_at|total_amount|order_number)$"),
    sort_order: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Items per page"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get user's orders with filtering and pagination"""
    try:
        filters = OrderFilters(
            status=status_filter,
            payment_status=payment_status,
            payment_method=payment_method,
            date_from=date_from,
            date_to=date_to,
            min_amount=min_amount,
            max_amount=max_amount,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        pagination = PaginationParams(page=page, limit=limit)
        orders, total = await order_manager.get_user_orders(current_user.id, filters, pagination)
        
        return paginated_response(
            data=orders,
            total=total,
            page=page,
            limit=limit,
            message="Orders retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Get user orders error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve orders"
        )

@router.get("/{order_id}", response_model=dict)
async def get_order(
    order_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get order by ID"""
    try:
        order = await order_manager.get_order_by_id(order_id, current_user.id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        return success_response(
            data=order,
            message="Order retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get order error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve order"
        )

@router.patch("/{order_id}", response_model=dict)
async def update_order(
    order_id: str,
    update_data: OrderUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update order (admin only for most fields)"""
    try:
        order = await order_manager.update_order(order_id, update_data, current_user.role)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        return success_response(
            data=order,
            message="Order updated successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update order error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Order update failed"
        )

@router.patch("/{order_id}/status", response_model=dict)
async def update_order_status(
    order_id: str,
    status_data: dict,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update order status (admin/designer only)"""
    # Check if user has permissions to update order status
    if current_user.role not in ["admin", "designer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin or designer role required."
        )
    
    try:
        # Extract status from request body
        new_status = status_data.get("status")
        if not new_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status is required"
            )
        
        # Validate status value
        try:
            status_enum = OrderStatus(new_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {new_status}"
            )
        
        # Create OrderUpdate object with just the status
        from .models import OrderUpdate
        update_data = OrderUpdate(status=status_enum)
        
        # Update the order
        order = await order_manager.update_order(order_id, update_data, current_user.role)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        return success_response(
            data=order,
            message="Order status updated successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update order status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Order status update failed"
        )

@router.post("/{order_id}/cancel", response_model=dict)
async def cancel_order(
    order_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Cancel order (only if pending or confirmed)"""
    try:
        success = await order_manager.cancel_order(order_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order cancellation failed"
            )
        
        return success_response(
            data={"cancelled": True},
            message="Order cancelled successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Cancel order error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Order cancellation failed"
        )

# Cart endpoints
cart_router = APIRouter(prefix="/cart", tags=["Cart"])

@cart_router.get("", response_model=dict)
async def get_cart(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get user's cart"""
    try:
        cart = await order_manager.get_user_cart(current_user.id)
        return success_response(
            data=cart,
            message="Cart retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Get cart error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cart"
        )

@cart_router.post("/items", response_model=dict)
async def add_to_cart(
    cart_item: CartItemCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Add item to cart"""
    try:
        async with db_manager.get_connection() as conn:
            # Check if product exists and is active
            product_row = await conn.fetchrow(
                "SELECT id, name, price, stock_quantity FROM products WHERE id = $1 AND is_active = true",
                cart_item.product_id
            )
            
            if not product_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Product not found"
                )
            
            # Check stock availability
            if product_row['stock_quantity'] < cart_item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient stock"
                )
            
            # Check if item already exists in cart
            existing_item = await conn.fetchrow(
                """
                SELECT id, quantity FROM cart_items 
                WHERE user_id = $1 AND product_id = $2 AND size = $3 AND color = $4
                """,
                current_user.id, cart_item.product_id, cart_item.size, cart_item.color
            )
            
            if existing_item:
                # Update existing item
                new_quantity = existing_item['quantity'] + cart_item.quantity
                if product_row['stock_quantity'] < new_quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Insufficient stock for requested quantity"
                    )
                
                await conn.execute(
                    "UPDATE cart_items SET quantity = $1, updated_at = $2 WHERE id = $3",
                    new_quantity, datetime.utcnow(), existing_item['id']
                )
            else:
                # Add new item
                import uuid
                await conn.execute(
                    """
                    INSERT INTO cart_items (id, user_id, product_id, quantity, size, color, customizations, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    str(uuid.uuid4()), current_user.id, cart_item.product_id, cart_item.quantity, 
                    cart_item.size, cart_item.color, cart_item.customizations, datetime.utcnow(), datetime.utcnow()
                )
            
            return success_response(
                data={"added": True, "product_name": product_row['name']},
                message="Item added to cart successfully"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add to cart error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add item to cart"
        )

@cart_router.patch("/items/{item_id}", response_model=dict)
async def update_cart_item(
    item_id: str,
    quantity: int = Query(..., gt=0, description="New quantity"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Update cart item quantity"""
    try:
        async with db_manager.get_connection() as conn:
            # Check if cart item exists and belongs to user
            cart_item = await conn.fetchrow(
                """
                SELECT ci.*, p.stock_quantity, p.name 
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.id
                WHERE ci.id = $1 AND ci.user_id = $2
                """,
                item_id, current_user.id
            )
            
            if not cart_item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cart item not found"
                )
            
            # Check stock availability
            if cart_item['stock_quantity'] < quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient stock"
                )
            
            # Update quantity
            await conn.execute(
                "UPDATE cart_items SET quantity = $1, updated_at = $2 WHERE id = $3",
                quantity, datetime.utcnow(), item_id
            )
            
            return success_response(
                data={"updated": True, "product_name": cart_item['name']},
                message="Cart item updated successfully"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update cart item error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update cart item"
        )

@cart_router.delete("/items/{item_id}", response_model=dict)
async def remove_from_cart(
    item_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Remove item from cart"""
    try:
        async with db_manager.get_connection() as conn:
            # Check if cart item exists and belongs to user
            cart_item = await conn.fetchrow(
                """
                SELECT ci.id, p.name 
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.id
                WHERE ci.id = $1 AND ci.user_id = $2
                """,
                item_id, current_user.id
            )
            
            if not cart_item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cart item not found"
                )
            
            # Remove item
            await conn.execute("DELETE FROM cart_items WHERE id = $1", item_id)
            
            return success_response(
                data={"removed": True, "product_name": cart_item['name']},
                message="Item removed from cart successfully"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove from cart error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove item from cart"
        )

@cart_router.delete("", response_model=dict)
async def clear_cart(
    current_user: UserResponse = Depends(get_current_user)
):
    """Clear user's cart"""
    try:
        async with db_manager.get_connection() as conn:
            await conn.execute("DELETE FROM cart_items WHERE user_id = $1", current_user.id)
            
            return success_response(
                data={"cleared": True},
                message="Cart cleared successfully"
            )
            
    except Exception as e:
        logger.error(f"Clear cart error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cart"
        )

# Cart router is now included directly in main.py
# router.include_router(cart_router)

# Admin endpoints for order management
admin_router = APIRouter(prefix="/admin/orders", tags=["Admin Orders"])

@admin_router.get("", response_model=dict)
async def get_all_orders(
    # Filtering parameters
    status_filter: Optional[OrderStatus] = Query(None, alias="status", description="Filter by order status"),
    payment_status: Optional[PaymentStatus] = Query(None, description="Filter by payment status"),
    payment_method: Optional[PaymentMethod] = Query(None, description="Filter by payment method"),
    date_from: Optional[datetime] = Query(None, description="Filter orders from date"),
    date_to: Optional[datetime] = Query(None, description="Filter orders to date"),
    min_amount: Optional[float] = Query(None, ge=0, description="Minimum order amount"),
    max_amount: Optional[float] = Query(None, ge=0, description="Maximum order amount"),
    search: Optional[str] = Query(None, description="Search in order number, customer name, email"),
    sort_by: Optional[str] = Query("created_at", pattern="^(created_at|updated_at|total_amount|order_number)$"),
    sort_order: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all orders (Admin only)"""
    if current_user.role not in ["admin", "designer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        filters = OrderFilters(
            status=status_filter,
            payment_status=payment_status,
            payment_method=payment_method,
            date_from=date_from,
            date_to=date_to,
            min_amount=min_amount,
            max_amount=max_amount,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        pagination = PaginationParams(page=page, limit=limit)
        
        # Get all orders (without user_id filter)
        async with db_manager.get_connection() as conn:
            # Build query conditions (similar to get_user_orders but without user_id filter)
            conditions = []
            params = []
            param_count = 0
            
            if filters.status:
                param_count += 1
                conditions.append(f"o.status = ${param_count}")
                params.append(filters.status.value)
            
            if filters.payment_status:
                param_count += 1
                conditions.append(f"o.payment_status = ${param_count}")
                params.append(filters.payment_status.value)
            
            if filters.date_from:
                param_count += 1
                conditions.append(f"o.created_at >= ${param_count}")
                params.append(filters.date_from)
            
            if filters.date_to:
                param_count += 1
                conditions.append(f"o.created_at <= ${param_count}")
                params.append(filters.date_to)
            
            if filters.min_amount:
                param_count += 1
                conditions.append(f"o.total_amount >= ${param_count}")
                params.append(filters.min_amount)
            
            if filters.max_amount:
                param_count += 1
                conditions.append(f"o.total_amount <= ${param_count}")
                params.append(filters.max_amount)
            
            if filters.search:
                param_count += 1
                conditions.append(f"(o.order_number ILIKE ${param_count} OR u.first_name ILIKE ${param_count} OR u.last_name ILIKE ${param_count} OR u.email ILIKE ${param_count})")
                params.extend([f"%{filters.search}%"] * 4)
                param_count += 3
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # Count total orders
            count_query = f"""
                SELECT COUNT(*) FROM orders o
                JOIN users u ON o.user_id = u.id
                WHERE {where_clause}
            """
            total = await conn.fetchval(count_query, *params)
            
            # Get orders with pagination
            orders_query = f"""
                SELECT o.*, u.first_name, u.last_name, u.email,
                       COUNT(oi.id) as items_count
                FROM orders o
                JOIN users u ON o.user_id = u.id
                LEFT JOIN order_items oi ON o.id = oi.order_id
                WHERE {where_clause}
                GROUP BY o.id, u.first_name, u.last_name, u.email
                ORDER BY o.{filters.sort_by} {filters.sort_order.upper()}
                LIMIT {pagination.limit} OFFSET {pagination.offset}
            """
            
            rows = await conn.fetch(orders_query, *params)
            
            orders = []
            for row in rows:
                order_data = OrderSummary(
                    id=row['id'],
                    order_number=row['order_number'],
                    status=OrderStatus(row['status']),
                    payment_status=PaymentStatus(row['payment_status']),
                    total_amount=row['total_amount'],
                    items_count=row['items_count'],
                    created_at=row['created_at']
                ).dict()
                
                # Add customer info
                order_data['customer'] = {
                    'name': f"{row['first_name']} {row['last_name']}",
                    'email': row['email']
                }
                orders.append(order_data)
            
            return paginated_response(
                data=orders,
                total=total,
                page=page,
                limit=limit,
                message="Orders retrieved successfully"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get all orders error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve orders"
        )

@admin_router.get("/{order_id}", response_model=dict)
async def get_order_admin(
    order_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get order by ID (Admin only)"""
    if current_user.role not in ["admin", "designer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        order = await order_manager.get_order_by_id(order_id)  # No user_id filter for admin
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        return success_response(
            data=order,
            message="Order retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get order admin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve order"
        )

# Include admin router
router.include_router(admin_router)