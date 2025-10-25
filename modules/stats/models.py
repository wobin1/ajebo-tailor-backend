from pydantic import BaseModel
from typing import Optional


class OrderStatsResponse(BaseModel):
    """Response model for order statistics"""
    pending_orders: int
    shipped_orders: int
    delivered_orders: int
    cancelled_orders: int
    pending_change: str
    shipped_change: str
    delivered_change: str
    cancelled_change: str


class DesignerStatsResponse(BaseModel):
    """Response model for designer dashboard statistics"""
    order_stats: OrderStatsResponse


class AdminStatsResponse(BaseModel):
    """Response model for admin dashboard statistics"""
    total_orders: int
    pending_orders: int
    shipped_orders: int
    delivered_orders: int
    cancelled_orders: int
    total_revenue: float
    orders_change: int
    revenue_change: float