import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from shared.db import db_manager
from .models import OrderStatsResponse, DesignerStatsResponse, AdminStatsResponse

logger = logging.getLogger(__name__)


class StatsManager:
    """Manager for handling statistics operations"""

    async def get_order_stats(self, user_id: str = None) -> OrderStatsResponse:
        """Get order statistics for designer dashboard"""
        try:
            async with db_manager.get_connection() as conn:
                # Get current counts by status
                current_query = """
                    SELECT 
                        status,
                        COUNT(*) as count
                    FROM orders 
                    GROUP BY status
                """
                
                results = await conn.fetch(current_query)
                
                # Initialize counts
                status_counts = {
                    'pending': 0,
                    'shipped': 0,
                    'delivered': 0,
                    'cancelled': 0
                }
                
                # Update with actual counts
                for row in results:
                    status = row['status']
                    count = row['count']
                    if status in status_counts:
                        status_counts[status] = count
                
                # Get today's counts for comparison (orders created today)
                today = datetime.now().date()
                today_query = """
                    SELECT 
                        status,
                        COUNT(*) as count
                    FROM orders 
                    WHERE DATE(created_at) = $1
                    GROUP BY status
                """
                
                today_results = await conn.fetch(today_query, today)
                
                today_counts = {
                    'pending': 0,
                    'shipped': 0,
                    'delivered': 0,
                    'cancelled': 0
                }
                
                for row in today_results:
                    status = row['status']
                    count = row['count']
                    if status in today_counts:
                        today_counts[status] = count
                
                # Format change messages
                def format_change(count: int, status: str) -> str:
                    if count > 0:
                        return f"+{count} new today"
                    elif count == 0:
                        return "No new orders today"
                    else:
                        return f"{count} today"
                
                return OrderStatsResponse(
                    pending_orders=status_counts['pending'],
                    shipped_orders=status_counts['shipped'],
                    delivered_orders=status_counts['delivered'],
                    cancelled_orders=status_counts['cancelled'],
                    pending_change=format_change(today_counts['pending'], 'pending'),
                    shipped_change=format_change(today_counts['shipped'], 'shipped'),
                    delivered_change=format_change(today_counts['delivered'], 'delivered'),
                    cancelled_change=format_change(today_counts['cancelled'], 'cancelled')
                )
                
        except Exception as e:
            logger.error(f"Error getting order stats: {str(e)}")
            # Return zero stats on database error
            return OrderStatsResponse(
                pending_orders=0,
                shipped_orders=0,
                delivered_orders=0,
                cancelled_orders=0,
                pending_change="Unable to load data",
                shipped_change="Unable to load data",
                delivered_change="Unable to load data",
                cancelled_change="Unable to load data"
            )

    async def get_designer_stats(self, user_id: str = None) -> DesignerStatsResponse:
        """Get comprehensive designer dashboard statistics"""
        try:
            order_stats = await self.get_order_stats(user_id)
            
            return DesignerStatsResponse(
                order_stats=order_stats
            )
            
        except Exception as e:
            logger.error(f"Error getting designer stats: {str(e)}")
            raise

    async def get_admin_stats(self) -> AdminStatsResponse:
        """Get comprehensive admin dashboard statistics"""
        try:
            async with db_manager.get_connection() as conn:
                # Get current counts by status
                current_query = """
                    SELECT 
                        status,
                        COUNT(*) as count,
                        COALESCE(SUM(total), 0) as revenue
                    FROM orders 
                    GROUP BY status
                """
                
                results = await conn.fetch(current_query)
                
                # Initialize counts
                status_counts = {
                    'pending': 0,
                    'shipped': 0,
                    'delivered': 0,
                    'cancelled': 0
                }
                
                total_orders = 0
                total_revenue = 0.0
                
                # Update with actual counts
                for row in results:
                    status = row['status']
                    count = row['count']
                    revenue = float(row['revenue']) if row['revenue'] else 0.0
                    
                    total_orders += count
                    total_revenue += revenue
                    
                    if status in status_counts:
                        status_counts[status] = count
                
                # Get yesterday's stats for comparison
                yesterday = datetime.now().date() - timedelta(days=1)
                yesterday_query = """
                    SELECT 
                        COUNT(*) as orders_count,
                        COALESCE(SUM(total), 0) as revenue
                    FROM orders 
                    WHERE DATE(created_at) = $1
                """
                
                yesterday_result = await conn.fetchrow(yesterday_query, yesterday)
                yesterday_orders = yesterday_result['orders_count'] if yesterday_result else 0
                yesterday_revenue = float(yesterday_result['revenue']) if yesterday_result and yesterday_result['revenue'] else 0.0
                
                # Get today's stats for comparison
                today = datetime.now().date()
                today_result = await conn.fetchrow(yesterday_query, today)
                today_orders = today_result['orders_count'] if today_result else 0
                today_revenue = float(today_result['revenue']) if today_result and today_result['revenue'] else 0.0
                
                # Calculate changes
                orders_change = today_orders - yesterday_orders
                revenue_change = today_revenue - yesterday_revenue
                
                return AdminStatsResponse(
                    total_orders=total_orders,
                    pending_orders=status_counts['pending'],
                    shipped_orders=status_counts['shipped'],
                    delivered_orders=status_counts['delivered'],
                    cancelled_orders=status_counts['cancelled'],
                    total_revenue=total_revenue,
                    orders_change=orders_change,
                    revenue_change=revenue_change
                )
                
        except Exception as e:
            logger.error(f"Error getting admin stats: {str(e)}")
            # Return zero stats on database error
            return AdminStatsResponse(
                total_orders=0,
                pending_orders=0,
                shipped_orders=0,
                delivered_orders=0,
                cancelled_orders=0,
                total_revenue=0.0,
                orders_change=0,
                revenue_change=0.0
            )


# Create global instance
stats_manager = StatsManager()