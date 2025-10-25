import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

from shared.db import db_manager
from shared.response import APIException, ValidationError, NotFoundError
from shared.utils import PaginationParams
from modules.orders.models import (
    OrderResponse, OrderSummary, OrderUpdate, OrderStatus, 
    PaymentStatus, OrderPriority, OrderFilters
)

logger = logging.getLogger(__name__)

class AdminOrderManager:
    """Admin order management business logic"""
    
    async def get_orders(
        self, 
        filters: Optional[OrderFilters] = None,
        pagination: Optional[PaginationParams] = None
    ) -> Dict[str, Any]:
        """Get all orders with filtering and pagination for admin"""
        try:
            logger.info("Getting orders with filters and pagination")
            async with db_manager.get_connection() as conn:
                # Build WHERE clause based on filters
                where_conditions = []
                params = []
                param_count = 1
                
                # By default, exclude cancelled orders unless specifically filtering for them
                if not filters or not filters.status or filters.status.value != 'cancelled':
                    where_conditions.append(f"o.status != ${param_count}")
                    params.append('cancelled')
                    param_count += 1
                
                if filters:
                    if filters.status:
                        where_conditions.append(f"o.status = ${param_count}")
                        params.append(filters.status.value)
                        param_count += 1
                        logger.info(f"Added status filter: {filters.status.value}")
                    
                    if filters.payment_status:
                        where_conditions.append(f"o.payment_status = ${param_count}")
                        params.append(filters.payment_status.value)
                        param_count += 1
                        logger.info(f"Added payment status filter: {filters.payment_status.value}")
                    
                    if filters.payment_method:
                        where_conditions.append(f"o.payment_method = ${param_count}")
                        params.append(filters.payment_method.value)
                        param_count += 1
                        logger.info(f"Added payment method filter: {filters.payment_method.value}")
                    
                    if filters.priority:
                        where_conditions.append(f"o.priority = ${param_count}")
                        params.append(filters.priority.value)
                        param_count += 1
                        logger.info(f"Added priority filter: {filters.priority.value}")
                    
                    if filters.date_from:
                        where_conditions.append(f"o.created_at >= ${param_count}")
                        params.append(filters.date_from)
                        param_count += 1
                        logger.info(f"Added date from filter: {filters.date_from}")
                    
                    if filters.date_to:
                        where_conditions.append(f"o.created_at <= ${param_count}")
                        params.append(filters.date_to)
                        param_count += 1
                        logger.info(f"Added date to filter: {filters.date_to}")
                    
                    if filters.min_amount:
                        where_conditions.append(f"o.total >= ${param_count}")
                        params.append(filters.min_amount)
                        param_count += 1
                        logger.info(f"Added min amount filter: {filters.min_amount}")
                    
                    if filters.max_amount:
                        where_conditions.append(f"o.total <= ${param_count}")
                        params.append(filters.max_amount)
                        param_count += 1
                        logger.info(f"Added max amount filter: {filters.max_amount}")
                    
                    if filters.search:
                        where_conditions.append(f"""(
                            o.order_number ILIKE ${param_count} OR 
                            u.name ILIKE ${param_count} OR 
                            u.email ILIKE ${param_count}
                        )""")
                        params.append(f"%{filters.search}%")
                        param_count += 1
                        logger.info(f"Added search filter: {filters.search}")

                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                # Build ORDER BY clause
                sort_by = filters.sort_by if filters else "created_at"
                sort_order = filters.sort_order if filters else "desc"
                order_clause = f"ORDER BY o.{sort_by} {sort_order.upper()}"

                # Count total orders
                count_query = f"""
                    SELECT COUNT(*)
                    FROM orders o
                    LEFT JOIN users u ON o.user_id = u.id
                    {where_clause}
                """
                
                logger.info("Getting total orders count")
                total_result = await conn.fetchrow(count_query, *params)
                total = total_result[0] if total_result else 0

                # Get orders with pagination
                page = pagination.page if pagination else 1
                limit = pagination.limit if pagination else 20
                offset = (page - 1) * limit
                
                orders_query = f"""
                    SELECT 
                        o.id, o.order_number, o.user_id, o.status, o.payment_status,
                        o.payment_method, o.priority, o.total as total_amount, o.created_at,
                        u.name, u.email,
                        COUNT(oi.id) as items_count
                    FROM orders o
                    LEFT JOIN users u ON o.user_id = u.id
                    LEFT JOIN order_items oi ON o.id = oi.order_id
                    {where_clause}
                    GROUP BY o.id, o.order_number, o.user_id, o.status, o.payment_status,
                             o.payment_method, o.priority, o.total, o.created_at, u.name, u.email
                    {order_clause}
                    LIMIT ${param_count} OFFSET ${param_count + 1}
                """
                
                params.extend([limit, offset])
                logger.info("Getting orders with pagination")
                orders_result = await conn.fetch(orders_query, *params)
                print("***** orders_result", orders_result)
                # Convert to OrderSummary objects
                orders = [
                    {
                        "id": row['id'],
                        "order_number": row['order_number'],
                        "status": row['status'],
                        "payment_status": row['payment_status'],
                        "priority": row['priority'],
                        "customer_name": row['name'],
                        "customer_email": row['email'],
                        "total": float(row['total_amount']),
                        "items_count": row['items_count'],
                        "created_at": row['created_at'].isoformat()
                    }
                    for row in orders_result
                ]

                return {
                    "orders": orders,
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "total_pages": (total + limit - 1) // limit
                }

        except Exception as e:
            logger.error(f"Failed to get orders: {str(e)}")
            raise APIException(500, f"Failed to get orders: {str(e)}")

    async def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific order by ID with full details"""
        try:
            async with db_manager.get_connection() as conn:
                # Get order details
                order_query = """
                    SELECT 
                        o.*, 
                        u.name, u.email
                    FROM orders o
                    LEFT JOIN users u ON o.user_id = u.id
                    WHERE o.id = $1
                """
                
                order_result = await conn.fetchrow(order_query, order_id)
                if not order_result:
                    return None

                # Get order items
                items_query = """
                    SELECT 
                        oi.id, oi.product_id, oi.product_name, oi.product_price, 
                        oi.quantity, oi.size, oi.color, oi.subtotal, oi.created_at,
                        p.slug as product_slug,
                        p.images[1] as product_image
                    FROM order_items oi
                    LEFT JOIN products p ON oi.product_id = p.id
                    WHERE oi.order_id = $1
                    ORDER BY oi.created_at
                """
                
                items_result = await conn.fetch(items_query, order_id)
                
                # Serialize order items using list comprehension
                order_items = [
                    {
                        **{k: v for k, v in dict(item).items() if k not in ['product_price', 'subtotal', 'created_at']},
                        "product_price": float(item['product_price']),
                        "subtotal": float(item['subtotal']),
                        "created_at": item['created_at'].isoformat()
                    }
                    for item in items_result
                ]

                # Serialize order data using dict comprehension with transformations
                numeric_fields = ['subtotal', 'tax_amount', 'shipping_amount', 'discount_amount', 'total']
                datetime_fields = ['created_at', 'updated_at']
                
                order_data = {
                    **{k: v for k, v in dict(order_result).items() 
                       if k not in numeric_fields + datetime_fields + ['name', 'email']},
                    **{field: float(order_result[field]) for field in numeric_fields},
                    **{field: order_result[field].isoformat() for field in datetime_fields},
                    "customer_name": order_result['name'],
                    "customer_email": order_result['email'],
                    "items": order_items,
                    "items_count": len(order_items)
                }

                return order_data

        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {str(e)}")
            raise APIException(500, f"Failed to get order: {str(e)}")

    async def update_order(self, order_id: str, order_data: OrderUpdate) -> Dict[str, Any]:
        """Update an order (admin only)"""
        try:
            async with db_manager.get_connection() as conn:
                # Check if order exists
                existing_order = await conn.fetchrow("SELECT id FROM orders WHERE id = $1", order_id)
                if not existing_order:
                    raise NotFoundError("Order not found")

                # Build update query dynamically
                update_fields = []
                params = []
                param_count = 1

                if order_data.status is not None:
                    update_fields.append(f"status = ${param_count}")
                    params.append(order_data.status.value)
                    param_count += 1

                if order_data.payment_status is not None:
                    update_fields.append(f"payment_status = ${param_count}")
                    params.append(order_data.payment_status.value)
                    param_count += 1

                if order_data.priority is not None:
                    update_fields.append(f"priority = ${param_count}")
                    params.append(order_data.priority.value)
                    param_count += 1

                if order_data.tracking_number is not None:
                    update_fields.append(f"tracking_number = ${param_count}")
                    params.append(order_data.tracking_number)
                    param_count += 1

                if order_data.notes is not None:
                    update_fields.append(f"notes = ${param_count}")
                    params.append(order_data.notes)
                    param_count += 1

                if not update_fields:
                    raise ValidationError("No fields to update")

                # Add updated_at
                update_fields.append(f"updated_at = ${param_count}")
                params.append(datetime.utcnow())
                param_count += 1

                # Add order_id for WHERE clause
                params.append(order_id)

                query = f"""
                    UPDATE orders 
                    SET {', '.join(update_fields)}
                    WHERE id = ${param_count}
                    RETURNING *
                """

                result = await conn.fetchrow(query, *params)
                
                # Get updated order details
                updated_order = await self.get_order_by_id(order_id)
                return updated_order

        except Exception as e:
            logger.error(f"Failed to update order {order_id}: {str(e)}")
            raise APIException(500, f"Failed to update order: {str(e)}")

    async def delete_order(self, order_id: str) -> bool:
        """Delete an order (admin only) - soft delete by setting status to cancelled"""
        try:
            async with db_manager.get_connection() as conn:
                # Check if order exists
                existing_order = await conn.fetchrow(
                    "SELECT id, status FROM orders WHERE id = $1", 
                    order_id
                )
                if not existing_order:
                    raise NotFoundError("Order not found")

                # Only allow deletion of pending or cancelled orders
                if existing_order['status'] in ['shipped', 'delivered']:
                    raise ValidationError("Cannot delete shipped or delivered orders")

                # Soft delete by setting status to cancelled
                await conn.execute(
                    """
                    UPDATE orders 
                    SET status = 'cancelled', updated_at = $1 
                    WHERE id = $2
                    """,
                    datetime.utcnow(),
                    order_id
                )

                return True

        except Exception as e:
            logger.error(f"Failed to delete order {order_id}: {str(e)}")
            raise APIException(500, f"Failed to delete order: {str(e)}")

    async def get_order_statistics(self) -> Dict[str, Any]:
        """Get order statistics for admin dashboard"""
        try:
            async with db_manager.get_connection() as conn:
                # Get order counts by status
                status_query = """
                    SELECT status, COUNT(*) as count
                    FROM orders
                    GROUP BY status
                """
                status_result = await conn.fetch(status_query)
                
                # Get payment status counts
                payment_query = """
                    SELECT payment_status, COUNT(*) as count
                    FROM orders
                    GROUP BY payment_status
                """
                payment_result = await conn.fetch(payment_query)
                
                # Get total revenue
                revenue_query = """
                    SELECT 
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as total_orders,
                        AVG(total_amount) as average_order_value
                    FROM orders
                    WHERE status != 'cancelled'
                """
                revenue_result = await conn.fetchrow(revenue_query)
                
                # Get recent orders count (last 30 days)
                recent_query = """
                    SELECT COUNT(*) as recent_orders
                    FROM orders
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                """
                recent_result = await conn.fetchrow(recent_query)

                return {
                    "order_status_counts": {row['status']: row['count'] for row in status_result},
                    "payment_status_counts": {row['payment_status']: row['count'] for row in payment_result},
                    "total_revenue": float(revenue_result['total_revenue'] or 0),
                    "total_orders": revenue_result['total_orders'],
                    "average_order_value": float(revenue_result['average_order_value'] or 0),
                    "recent_orders_30_days": recent_result['recent_orders']
                }

        except Exception as e:
            logger.error(f"Failed to get order statistics: {str(e)}")
            raise APIException(500, f"Failed to get order statistics: {str(e)}")

