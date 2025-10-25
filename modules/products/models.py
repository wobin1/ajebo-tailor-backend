from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    image: Optional[str]
    parent_id: Optional[str]
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

class ProductResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    price: Decimal
    original_price: Optional[Decimal]
    category_id: Optional[str]
    subcategory_id: Optional[str]
    images: List[str]
    sizes: List[str]
    colors: List[str]
    tags: List[str]
    in_stock: bool
    stock_quantity: int
    featured: bool
    is_active: bool
    sku: Optional[str]
    weight: Optional[Decimal]
    dimensions: Optional[dict]
    meta_title: Optional[str]
    meta_description: Optional[str]
    created_at: datetime
    updated_at: datetime

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: Decimal = Field(..., gt=0)
    original_price: Optional[Decimal] = Field(None, gt=0)
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    images: List[str] = []
    sizes: List[str] = []
    colors: List[str] = []
    tags: List[str] = []
    stock_quantity: int = Field(default=0, ge=0)
    featured: bool = False
    sku: Optional[str] = None
    weight: Optional[Decimal] = Field(None, gt=0)
    dimensions: Optional[dict] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0)
    original_price: Optional[Decimal] = Field(None, gt=0)
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    images: Optional[List[str]] = None
    sizes: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    in_stock: Optional[bool] = None
    stock_quantity: Optional[int] = Field(None, ge=0)
    featured: Optional[bool] = None
    sku: Optional[str] = None
    weight: Optional[Decimal] = Field(None, gt=0)
    dimensions: Optional[dict] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

class ProductFilters(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    search: Optional[str] = None
    min_price: Optional[Decimal] = Field(None, ge=0)
    max_price: Optional[Decimal] = Field(None, ge=0)
    colors: Optional[List[str]] = None
    sizes: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    featured: Optional[bool] = None
    in_stock: Optional[bool] = None
    sort_by: Optional[str] = Field(default="created_at", pattern="^(name|price|created_at|updated_at|featured|stock_quantity)$")
    sort_order: Optional[str] = Field(default="desc", pattern="^(asc|desc)$")

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    image: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: int = Field(default=0, ge=0)

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    image: Optional[str] = None
    parent_id: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)