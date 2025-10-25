from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
import logging

from shared.response import success_response, paginated_response, APIException
from shared.utils import PaginationParams
from modules.auth.router import get_current_user, get_current_user_optional
from modules.auth.models import UserResponse
from .models import (
    ProductResponse, ProductCreate, ProductUpdate, ProductFilters,
    CategoryResponse, CategoryCreate, CategoryUpdate
)
from .manager import product_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("", response_model=dict)
async def get_products(
    # Filtering parameters
    category: Optional[str] = Query(None, description="Filter by category slug"),
    subcategory: Optional[str] = Query(None, description="Filter by subcategory slug"),
    search: Optional[str] = Query(None, description="Search in name, description, and tags"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
    colors: Optional[List[str]] = Query(None, description="Filter by colors"),
    sizes: Optional[List[str]] = Query(None, description="Filter by sizes"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    featured: Optional[bool] = Query(None, description="Filter by featured products"),
    in_stock: Optional[bool] = Query(None, description="Filter by stock availability"),
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc"),
    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(12, ge=1, le=100, description="Items per page"),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """Get products with filtering and pagination"""
    try:
        filters = ProductFilters(
            category=category,
            subcategory=subcategory,
            search=search,
            min_price=min_price,
            max_price=max_price,
            colors=colors,
            sizes=sizes,
            tags=tags,
            featured=featured,
            in_stock=in_stock,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        pagination = PaginationParams(page=page, limit=limit)
        products, total = await product_manager.get_products(filters, pagination)
        
        return paginated_response(
            data=[product.dict() for product in products],
            total=total,
            page=page,
            limit=limit,
            message="Products retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Get products error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve products"
        )

@router.get("/featured", response_model=dict)
async def get_featured_products(
    limit: int = Query(4, ge=1, le=20, description="Number of featured products"),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """Get featured products"""
    try:
        filters = ProductFilters(featured=True)
        pagination = PaginationParams(page=1, limit=limit)
        products, total = await product_manager.get_products(filters, pagination)
        
        return success_response(
            data=[product.dict() for product in products],
            message="Featured products retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Get featured products error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve featured products"
        )

@router.get("/search", response_model=dict)
async def search_products(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """Search products"""
    try:
        filters = ProductFilters(search=q)
        pagination = PaginationParams(page=1, limit=limit)
        products, total = await product_manager.get_products(filters, pagination)
        
        return success_response(
            data=[product.dict() for product in products],
            meta={"total": total, "query": q},
            message="Search results retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Search products error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )

@router.get("/{product_id}", response_model=dict)
async def get_product(
    product_id: str,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """Get product by ID or slug"""
    try:
        # Try to get by ID first, then by slug
        product = await product_manager.get_product_by_id(product_id)
        if not product:
            product = await product_manager.get_product_by_slug(product_id)
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        
        return success_response(
            data=product.dict(),
            message="Product retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get product error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve product"
        )

@router.get("/{product_id}/related", response_model=dict)
async def get_related_products(
    product_id: str,
    limit: int = Query(4, ge=1, le=20, description="Number of related products"),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """Get related products"""
    try:
        # Get the main product first
        product = await product_manager.get_product_by_id(product_id)
        if not product:
            product = await product_manager.get_product_by_slug(product_id)
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        
        # Get related products from same category
        filters = ProductFilters(category=product.category_id if product.category_id else None)
        pagination = PaginationParams(page=1, limit=limit + 1)  # +1 to exclude the current product
        products, total = await product_manager.get_products(filters, pagination)
        
        # Remove the current product from results
        related_products = [p for p in products if p.id != product.id][:limit]
        
        return success_response(
            data=[product.dict() for product in related_products],
            message="Related products retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get related products error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve related products"
        )

# Admin endpoints (require authentication and admin role)
@router.post("", response_model=dict)
async def create_product(
    product_data: ProductCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create new product (Admin only)"""
    if current_user.role not in ["admin", "designer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        product = await product_manager.create_product(product_data)
        return success_response(
            data=product.dict(),
            message="Product created successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Create product error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Product creation failed"
        )

# Categories endpoints
categories_router = APIRouter(prefix="/categories", tags=["Categories"])

@categories_router.get("", response_model=dict)
async def get_categories(
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """Get all categories"""
    try:
        categories = await product_manager.get_categories()
        return success_response(
            data=[category.dict() for category in categories],
            message="Categories retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Get categories error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve categories"
        )

@categories_router.get("/{category_id}", response_model=dict)
async def get_category(
    category_id: str,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """Get category by ID or slug"""
    try:
        # Try to get by ID first, then by slug
        category = await product_manager.get_category_by_id(category_id)
        if not category:
            category = await product_manager.get_category_by_slug(category_id)
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        
        return success_response(
            data=category.dict(),
            message="Category retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get category error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve category"
        )

@categories_router.post("", response_model=dict)
async def create_category(
    category_data: CategoryCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create new category (Admin only)"""
    if current_user.role not in ["admin", "designer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        category = await product_manager.create_category(category_data)
        return success_response(
            data=category.dict(),
            message="Category created successfully"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Create category error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Category creation failed"
        )

# Include categories router
router.include_router(categories_router)