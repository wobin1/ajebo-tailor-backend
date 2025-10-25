import logging
from typing import List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
import uuid

from shared.db import db_manager
from shared.response import APIException, ValidationError, NotFoundError, ConflictError
from shared.utils import generate_order_number, calculate_tax, calculate_shipping_cost, PaginationParams
from .models import (
    OrderCreate, OrderUpdate, OrderResponse, OrderSummary, OrderItemResponse,
    CartItemResponse, CartSummary, PaymentCreate, PaymentResponse,
    OrderFilters, OrderStatus, PaymentStatus, PaymentMethod, OrderPriority
)


logger = logging.getLogger(__name__)

class OrderManager:
    """Order management business logic"""
    
    async def create_order(self, user_id: str, order_data: OrderCreate) :
        """Create a new order"""
        print("** process 1 hit **")
        try:
            async with db_manager.get_connection() as conn:
                async with conn.transaction():
                    print("** process 2 hit **")
                    # Generate order number
                    order_number = generate_order_number()
                    order_id = str(uuid.uuid4())
                    
                    print("** process 3 hit **")
                    # Validate addresses (optional for designer orders)
                    shipping_address = None
                    billing_address = None
                    if order_data.shipping_address_id:
                        print(f"** Validating shipping address: {order_data.shipping_address_id} for user: {user_id} **")
                        shipping_address = await self._get_user_address(conn, user_id, order_data.shipping_address_id)
                        billing_address_id = order_data.billing_address_id or order_data.shipping_address_id
                        print(f"** Validating billing address: {billing_address_id} for user: {user_id} **")
                        billing_address = await self._get_user_address(conn, user_id, billing_address_id)
                    else:
                        # For designer orders without address, use empty dict
                        shipping_address = {}
                        billing_address = {}

                    print("** process 4 hit **")
                    # Validate and calculate order totals
                    print(f"** Validating {len(order_data.items)} order items **")
                    subtotal, items_data = await self._validate_order_items(conn, order_data.items)
                    print(f"** Items validated. Subtotal: {subtotal} **")
                    
                    print("** process 5 hit **")
                    # Apply coupon if provided
                    coupon_discount = Decimal('0')
                    coupon_code = None
                    if order_data.coupon_code:
                        coupon_discount, coupon_code = await self._apply_coupon(conn, order_data.coupon_code, subtotal)
                 
                    print("** process 6 hit **")
                    # Calculate costs
                    tax_amount = calculate_tax(subtotal - coupon_discount)
                    shipping_cost = calculate_shipping_cost(subtotal, shipping_address) if shipping_address else Decimal('0')
                    total_amount = subtotal + tax_amount + shipping_cost - coupon_discount
                    
                    print("** process 7 hit **")
                    # Create order
                    order_query = """
                        INSERT INTO orders (
                            id, order_number, user_id, status, payment_status, payment_method, priority,
                            subtotal, tax_amount, shipping_amount, discount_amount, total,
                            shipping_address_id, billing_address_id,
                            notes, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                        RETURNING *
                    """
                    payment_method_value = order_data.payment_method.value if order_data.payment_method else None
                    priority_value = order_data.priority.value if order_data.priority else OrderPriority.MEDIUM.value
                    order_row = await conn.fetchrow(
                        order_query,
                        order_id, order_number, user_id, OrderStatus.PENDING.value, 
                        PaymentStatus.PENDING.value, payment_method_value, priority_value,
                        subtotal, tax_amount, shipping_cost, coupon_discount, total_amount,
                        order_data.shipping_address_id, order_data.billing_address_id,
                        order_data.notes, datetime.utcnow(), datetime.utcnow()
                    )
                    
                    print("** process 8 hit **")
                    # Create order items
                    order_items = []
                    for item_data, product_info in zip(order_data.items, items_data):
                        item_id = str(uuid.uuid4())
                        unit_price = product_info['price']
                        total_price = unit_price * item_data.quantity
                        
                        item_query = """
                            INSERT INTO order_items (
                                id, order_id, product_id, product_name, quantity, size, color,
                                product_price, subtotal, created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                            RETURNING *
                        """
                        print("** process 9 hit **")
                        item_row = await conn.fetchrow(
                            item_query,
                            item_id, order_id, item_data.product_id, product_info['name'],
                            item_data.quantity, item_data.size, item_data.color, 
                            unit_price, total_price, datetime.utcnow()
                        )
                        
                        print("** process 10 hit **")
                        
                        
                        print("** process 11 hit **")
                        # Update product stock
                        await conn.execute(
                            "UPDATE products SET stock_quantity = stock_quantity - $1 WHERE id = $2",
                            item_data.quantity, item_data.product_id
                        )
                    
                    print("** process 12 hit **")
                    # Clear user's cart after successful order
                    await conn.execute("DELETE FROM cart_items WHERE user_id = $1", user_id)
                    
                    print("** process 13 hit **")
                    return order_row['id']
                    
        except APIException:
            raise
        except Exception as e:
            logger.error(f"Create order error: {e}")
            raise APIException(500, "Order creation failed")
    
    async def get_user_orders(self, user_id: str, filters: OrderFilters, pagination: PaginationParams):
        """Get user's orders with filtering and pagination"""
        try:
            async with db_manager.get_connection() as conn:
                # Build query conditions
                conditions = ["user_id = $1"]
                params = [user_id]
                param_count = 1
                
                if filters.status:
                    param_count += 1
                    conditions.append(f"status = ${param_count}")
                    params.append(filters.status.value)
                
                if filters.payment_status:
                    param_count += 1
                    conditions.append(f"payment_status = ${param_count}")
                    params.append(filters.payment_status.value)
                
                if filters.date_from:
                    param_count += 1
                    conditions.append(f"created_at >= ${param_count}")
                    params.append(filters.date_from)
                
                if filters.date_to:
                    param_count += 1
                    conditions.append(f"created_at <= ${param_count}")
                    params.append(filters.date_to)
                
                if filters.min_amount:
                    param_count += 1
                    conditions.append(f"total_amount >= ${param_count}")
                    params.append(filters.min_amount)
                
                if filters.max_amount:
                    param_count += 1
                    conditions.append(f"total_amount <= ${param_count}")
                    params.append(filters.max_amount)
                
                if filters.priority:
                    param_count += 1
                    conditions.append(f"priority = ${param_count}")
                    params.append(filters.priority.value)
                
                if filters.search:
                    param_count += 1
                    conditions.append(f"order_number ILIKE ${param_count}")
                    params.append(f"%{filters.search}%")
                
                where_clause = " AND ".join(conditions)
                
                # Count total orders
                count_query = f"SELECT COUNT(*) FROM orders WHERE {where_clause}"
                total = await conn.fetchval(count_query, *params)
                
                # Get orders with pagination
                orders_query = f"""
                    SELECT o.*, 
                           u.name as customer_name,
                           u.email as customer_email,
                           COUNT(oi.id) as items_count
                    FROM orders o
                    LEFT JOIN users u ON o.user_id = u.id
                    LEFT JOIN order_items oi ON o.id = oi.order_id
                    WHERE {where_clause}
                    GROUP BY o.id, u.name, u.email
                    ORDER BY o.{filters.sort_by} {filters.sort_order.upper()}
                    LIMIT {pagination.limit} OFFSET {pagination.offset}
                """
                
                rows = await conn.fetch(orders_query, *params)

                orders =[dict(row) for row in rows] if rows else []
                print(orders)
                
                return orders, total
                
        except Exception as e:
            logger.error(f"Get user orders error: {e}")
            raise APIException(500, "Failed to retrieve orders")
    
    async def get_order_by_id(self, order_id: str, user_id: Optional[str] = None) -> Optional[OrderResponse]:
        """Get order by ID"""
        try:
            async with db_manager.get_connection() as conn:
                # Build query conditions
                conditions = ["o.id = $1"]
                params = [order_id]
                
                if user_id:
                    conditions.append("o.user_id = $2")
                    params.append(user_id)
                
                where_clause = " AND ".join(conditions)
                
                order_query = f"""
                    SELECT o.*, 
                           u.name as customer_name,
                           u.email as customer_email
                    FROM orders o
                    LEFT JOIN users u ON o.user_id = u.id
                    WHERE {where_clause}
                """
                
                order_row = await conn.fetchrow(order_query, *params)
                if not order_row:
                    return None

                order_row = dict(order_row) if order_row else {}
                
                # Get order items
                items_query = """
                    SELECT oi.*, p.name as product_name, p.slug as product_slug, p.images as product_images
                    FROM order_items oi
                    JOIN products p ON oi.product_id = p.id
                    WHERE oi.order_id = $1
                    ORDER BY oi.created_at
                """
                
                item_rows = await conn.fetch(items_query, order_id)

                order_items = [dict(row) for row in item_rows] if item_rows else []
                
                # Add items to order data
                order_row["items"] = order_items
                order_row["items_count"] = len(order_items)
                
                return order_row
                
        except Exception as e:
            logger.error(f"Get order by ID error: {e}")
            raise APIException(500, "Failed to retrieve order")
    
    async def update_order(self, order_id: str, update_data: OrderUpdate, user_role: str = "customer") -> Optional[OrderResponse]:
        """Update order (admin only for most fields)"""
        try:
            async with db_manager.get_connection() as conn:
                async with conn.transaction():
                    # Check if order exists
                    existing_order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
                    if not existing_order:
                        raise NotFoundError("Order not found")
                    
                    # Build update fields
                    update_fields = []
                    params = []
                    param_count = 0
                    
                    # Only admin can update status and payment status
                    if user_role in ["admin", "designer"]:
                        if update_data.status:
                            param_count += 1
                            update_fields.append(f"status = ${param_count}")
                            params.append(update_data.status.value)
                        
                        if update_data.payment_status:
                            param_count += 1
                            update_fields.append(f"payment_status = ${param_count}")
                            params.append(update_data.payment_status.value)
                        
                        if update_data.priority:
                            param_count += 1
                            update_fields.append(f"priority = ${param_count}")
                            params.append(update_data.priority.value)
                        
                        if update_data.tracking_number is not None:
                            param_count += 1
                            update_fields.append(f"tracking_number = ${param_count}")
                            params.append(update_data.tracking_number)
                    
                    if update_data.notes is not None:
                        param_count += 1
                        update_fields.append(f"notes = ${param_count}")
                        params.append(update_data.notes)
                    
                    if not update_fields:
                        # No valid updates
                        return await self.get_order_by_id(order_id)
                    
                    # Add updated_at
                    param_count += 1
                    update_fields.append(f"updated_at = ${param_count}")
                    params.append(datetime.utcnow())
                    
                    # Add order_id for WHERE clause
                    param_count += 1
                    params.append(order_id)
                    
                    # Update query with debug logging
                    update_query = f"""
                        UPDATE orders 
                        SET {', '.join(update_fields)}
                        WHERE id = ${param_count}
                    """
                    
                    logger.info(f"Executing update query: {update_query}")
                    logger.info(f"With parameters: {params}")
                    
                    result = await conn.execute(update_query, *params)
                    logger.info(f"Update result: {result}")
                    
                    # Return updated order
                    return await self.get_order_by_id(order_id)
                
        except APIException:
            raise
        except Exception as e:
            logger.error(f"Update order error: {e}")
            raise APIException(500, "Order update failed")
    
    async def cancel_order(self, order_id: str, user_id: str) -> bool:
        """Cancel order (only if pending or confirmed)"""
        try:
            async with db_manager.get_connection() as conn:
                async with conn.transaction():
                    # Check if order exists and belongs to user
                    order_row = await conn.fetchrow(
                        "SELECT * FROM orders WHERE id = $1 AND user_id = $2",
                        order_id, user_id
                    )
                    
                    if not order_row:
                        raise NotFoundError("Order not found")
                    
                    # Check if order can be cancelled
                    current_status = OrderStatus(order_row['status'])
                    if current_status not in [OrderStatus.PENDING, OrderStatus.CONFIRMED]:
                        raise ConflictError("Order cannot be cancelled")
                    
                    # Update order status
                    await conn.execute(
                        "UPDATE orders SET status = $1, updated_at = $2 WHERE id = $3",
                        OrderStatus.CANCELLED.value, datetime.utcnow(), order_id
                    )
                    
                    # Restore product stock
                    items_query = "SELECT product_id, quantity FROM order_items WHERE order_id = $1"
                    items = await conn.fetch(items_query, order_id)
                    
                    for item in items:
                        await conn.execute(
                            "UPDATE products SET stock_quantity = stock_quantity + $1 WHERE id = $2",
                            item['quantity'], item['product_id']
                        )
                    
                    return True
                    
        except APIException:
            raise
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            raise APIException(500, "Order cancellation failed")
    
    async def get_user_cart(self, user_id: str) -> CartSummary:
        """Get user's cart with items and totals"""
        try:
            async with db_manager.get_connection() as conn:
                cart_query = """
                    SELECT ci.*, p.name, p.slug, p.images, p.price, p.stock_quantity
                    FROM cart_items ci
                    JOIN products p ON ci.product_id = p.id
                    WHERE ci.user_id = $1
                    ORDER BY ci.created_at DESC
                """
                
                rows = await conn.fetch(cart_query, user_id)
                
                cart_items = [dict(row) for row in rows] if rows else []
                subtotal = sum(item['price'] * item['quantity'] for item in cart_items)
                
                estimated_tax = calculate_tax(subtotal)
                estimated_shipping = calculate_shipping_cost(subtotal, {})  # Default shipping
                estimated_total = subtotal + estimated_tax + estimated_shipping
                
                return {
                    "items": cart_items,
                    "items_count": len(cart_items),
                    "subtotal": float(subtotal),
                    "estimated_tax": float(estimated_tax),
                    "estimated_shipping": float(estimated_shipping),
                    "estimated_total": float(estimated_total)
                }
                
        except Exception as e:
            logger.error(f"Get user cart error: {e}")
            raise APIException(500, "Failed to retrieve cart")
    
    # Helper methods
    async def _get_user_address(self, conn, user_id: str, address_id: str) -> dict:
        """Get user address by ID"""
        # First check if address exists at all
        address_exists = await conn.fetchrow(
            "SELECT id, user_id FROM addresses WHERE id = $1",
            address_id
        )
        
        print(f"** Address lookup result: {dict(address_exists) if address_exists else 'None'} **")
        
        if not address_exists:
            error_msg = f"Address {address_id} does not exist"
            logger.error(error_msg)
            raise ValidationError(error_msg)
        
        # Convert UUID to string for comparison
        address_user_id = str(address_exists['user_id'])
        if address_user_id != user_id:
            error_msg = f"Address {address_id} does not belong to user {user_id}. It belongs to user {address_user_id}"
            logger.error(error_msg)
            raise ValidationError(error_msg)
        
        address_row = await conn.fetchrow(
            "SELECT * FROM addresses WHERE id = $1 AND user_id = $2",
            address_id, user_id
        )
        
        print(f"** Full address data: {dict(address_row) if address_row else 'None'} **")
        
        if not address_row:
            error_msg = "Invalid address ID"
            logger.error(error_msg)
            raise ValidationError(error_msg)
        
        return dict(address_row)
    
    async def _validate_order_items(self, conn, items) -> Tuple[Decimal, List[dict]]:
        """Validate order items and calculate subtotal"""
        subtotal = Decimal('0')
        items_data = []
        
        for item in items:
            print(f"** Validating product: {item.product_id} **")
            # Get product info
            product_row = await conn.fetchrow(
                "SELECT id, name, slug, price, stock_quantity, images FROM products WHERE id = $1 AND is_active = true",
                item.product_id
            )
            
            print(f"** Product lookup result: {dict(product_row) if product_row else 'None'} **")
            
            if not product_row:
                error_msg = f"Product {item.product_id} not found or inactive"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            
            # Check stock
            if product_row['stock_quantity'] < item.quantity:
                error_msg = f"Insufficient stock for product {product_row['name']}. Available: {product_row['stock_quantity']}, Requested: {item.quantity}"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            
            item_total = product_row['price'] * item.quantity
            subtotal += item_total
            
            items_data.append({
                'id': product_row['id'],
                'name': product_row['name'],
                'slug': product_row['slug'],
                'price': product_row['price'],
                'images': product_row['images']
            })
        
        return subtotal, items_data
    
    async def _apply_coupon(self, conn, coupon_code: str, subtotal: Decimal) -> Tuple[Decimal, str]:
        """Apply coupon and return discount amount"""
        coupon_row = await conn.fetchrow(
            """
            SELECT * FROM coupons 
            WHERE code = $1 AND is_active = true 
            AND (expires_at IS NULL OR expires_at > NOW())
            AND (usage_limit IS NULL OR used_count < usage_limit)
            """,
            coupon_code
        )
        
        if not coupon_row:
            raise ValidationError("Invalid or expired coupon code")
        
        # Check minimum order amount
        if coupon_row['min_order_amount'] and subtotal < coupon_row['min_order_amount']:
            raise ValidationError(f"Minimum order amount of ${coupon_row['min_order_amount']} required for this coupon")
        
        # Calculate discount
        if coupon_row['discount_type'] == 'percentage':
            discount = subtotal * (coupon_row['discount_value'] / 100)
            if coupon_row['max_discount_amount']:
                discount = min(discount, coupon_row['max_discount_amount'])
        else:  # fixed amount
            discount = min(coupon_row['discount_value'], subtotal)
        
        # Update coupon usage
        await conn.execute(
            "UPDATE coupons SET used_count = used_count + 1 WHERE id = $1",
            coupon_row['id']
        )
        
        return discount, coupon_code

# Create global instance
order_manager = OrderManager()