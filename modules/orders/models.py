from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentMethod(str, Enum):
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    CASH_ON_DELIVERY = "cash_on_delivery"
    MOBILE_MONEY = "mobile_money"

class OrderPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

# Order Item Models
class OrderItemCreate(BaseModel):
    product_id: str = Field(..., description="Product ID")
    quantity: int = Field(..., gt=0, description="Quantity ordered")
    size: Optional[str] = Field(None, description="Selected size")
    color: Optional[str] = Field(None, description="Selected color")
    customizations: Optional[dict] = Field(None, description="Custom requirements")

class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    product_slug: str
    product_image: Optional[str]
    quantity: int
    size: Optional[str]
    color: Optional[str]
    unit_price: Decimal
    total_price: Decimal
    customizations: Optional[dict]
    created_at: datetime

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }

# Order Models
class OrderCreate(BaseModel):
    items: List[OrderItemCreate] = Field(..., min_items=1, description="Order items")
    shipping_address_id: Optional[str] = Field(None, description="Shipping address ID")
    billing_address_id: Optional[str] = Field(None, description="Billing address ID (defaults to shipping)")
    payment_method: Optional[PaymentMethod] = Field(None, description="Payment method")
    priority: Optional[OrderPriority] = Field(OrderPriority.MEDIUM, description="Order priority")
    coupon_code: Optional[str] = Field(None, description="Coupon code")
    notes: Optional[str] = Field(None, max_length=500, description="Order notes")

    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError("Order must contain at least one item")
        return v

class DesignerOrderCreate(BaseModel):
    items: List[OrderItemCreate] = Field(..., min_items=1, description="Order items")
    payment_method: Optional[PaymentMethod] = Field(None, description="Payment method")
    priority: Optional[OrderPriority] = Field(OrderPriority.MEDIUM, description="Order priority")
    notes: Optional[str] = Field(None, max_length=500, description="Order notes")

    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError("Order must contain at least one item")
        return v

class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = Field(None, description="Order status")
    payment_status: Optional[PaymentStatus] = Field(None, description="Payment status")
    priority: Optional[OrderPriority] = Field(None, description="Order priority")
    tracking_number: Optional[str] = Field(None, description="Shipping tracking number")
    notes: Optional[str] = Field(None, max_length=500, description="Order notes")

class OrderResponse(BaseModel):
    id: str
    order_number: str
    user_id: str
    customer_name: Optional[str]
    customer_email: Optional[str]
    status: OrderStatus
    payment_status: PaymentStatus
    payment_method: PaymentMethod
    priority: OrderPriority
    items: List[OrderItemResponse]
    subtotal: Decimal
    tax_amount: Decimal
    shipping_cost: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    coupon_code: Optional[str]
    coupon_discount: Optional[Decimal]
    shipping_address: dict
    billing_address: dict
    tracking_number: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }

class OrderSummary(BaseModel):
    id: str
    order_number: str
    status: OrderStatus
    payment_status: PaymentStatus
    priority: OrderPriority
    customer_name: Optional[str]
    customer_email: Optional[str]
    total_amount: Decimal
    items_count: int
    created_at: datetime

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }

# Order Filters
class OrderFilters(BaseModel):
    status: Optional[OrderStatus] = None
    payment_status: Optional[PaymentStatus] = None
    payment_method: Optional[PaymentMethod] = None
    priority: Optional[OrderPriority] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    search: Optional[str] = None  # Search in order number, customer name, email
    sort_by: str = Field("created_at", pattern="^(created_at|updated_at|total_amount|order_number|priority)$")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")

# Cart Models (for cart-to-order conversion)
class CartItemCreate(BaseModel):
    product_id: str = Field(..., description="Product ID")
    quantity: int = Field(..., gt=0, description="Quantity to add")
    size: Optional[str] = Field(None, description="Product size")
    color: Optional[str] = Field(None, description="Product color")
    customizations: Optional[dict] = Field(None, description="Custom requirements")

class CartItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    product_slug: str
    product_image: Optional[str]
    product_price: Decimal
    quantity: int
    size: Optional[str]
    color: Optional[str]
    customizations: Optional[dict]
    subtotal: Decimal
    in_stock: bool
    created_at: datetime

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }

class CartSummary(BaseModel):
    items: List[CartItemResponse]
    items_count: int
    subtotal: Decimal
    estimated_tax: Decimal
    estimated_shipping: Decimal
    estimated_total: Decimal

    class Config:
        json_encoders = {
            Decimal: str
        }

# Payment Models
class PaymentCreate(BaseModel):
    order_id: str
    payment_method: PaymentMethod
    amount: Decimal
    payment_reference: Optional[str] = Field(None, description="External payment reference")
    payment_data: Optional[dict] = Field(None, description="Payment gateway specific data")

class PaymentResponse(BaseModel):
    id: str
    order_id: str
    payment_method: PaymentMethod
    amount: Decimal
    status: PaymentStatus
    payment_reference: Optional[str]
    transaction_id: Optional[str]
    gateway_response: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }