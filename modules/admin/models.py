"""
Admin-related Pydantic models
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class AdminUserResponse(BaseModel):
    """Response model for admin user data"""
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: str
    is_active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime


class AdminOrderResponse(BaseModel):
    """Response model for admin order data"""
    id: str
    user_id: str
    status: str
    payment_status: str
    total: float
    shipping_address: dict
    created_at: datetime
    updated_at: datetime


class AdminProductResponse(BaseModel):
    """Response model for admin product data"""
    id: str
    name: str
    description: Optional[str]
    price: float
    original_price: Optional[float]
    sku: Optional[str]
    stock_quantity: int
    category_id: Optional[str]
    category_name: Optional[str]
    subcategory_id: Optional[str]
    subcategory_name: Optional[str]
    colors: List[str]
    sizes: List[str]
    tags: List[str]
    images: List[str]
    featured: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductCreateRequest(BaseModel):
    """Request model for creating a product"""
    name: str
    description: Optional[str]
    price: Decimal
    original_price: Optional[Decimal]
    sku: Optional[str]
    stock_quantity: int = 0
    category_id: Optional[str]
    subcategory_id: Optional[str]
    colors: List[str] = []
    sizes: List[str] = []
    tags: List[str] = []
    images: List[str] = []
    featured: bool = False
    is_active: bool = True


class ProductUpdateRequest(BaseModel):
    """Request model for updating a product"""
    name: Optional[str]
    description: Optional[str]
    price: Optional[Decimal]
    original_price: Optional[Decimal]
    sku: Optional[str]
    stock_quantity: Optional[int]
    category_id: Optional[str]
    subcategory_id: Optional[str]
    colors: Optional[List[str]]
    sizes: Optional[List[str]]
    tags: Optional[List[str]]
    images: Optional[List[str]]
    featured: Optional[bool]
    is_active: Optional[bool]


class UpdateUserRoleRequest(BaseModel):
    """Request model for updating user role"""
    role: str


class UpdateUserStatusRequest(BaseModel):
    """Request model for updating user status"""
    is_active: bool


class UserCreateRequest(BaseModel):
    """Request model for creating a new user"""
    email: str
    name: str
    password: str
    role: str = "customer"
    is_active: bool = True
    phone: Optional[str] = None


class UserUpdateRequest(BaseModel):
    """Request model for updating user information"""
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    phone: Optional[str] = None


class UserDetailResponse(BaseModel):
    """Detailed response model for user data with additional stats"""
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    profile: Optional[dict] = None
    order_count: int = 0
    total_spent: float = 0.0