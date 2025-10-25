"""
Admin router for administrative endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
import asyncpg

from shared.db import get_db_connection, db_manager
from shared.auth import get_current_user, require_admin
from shared.response import success_response, error_response
from .manager import AdminManager
from .product_manager import admin_product_manager
from .models import ProductCreateRequest, ProductUpdateRequest, UserCreateRequest, UserUpdateRequest
from .order_router import router as order_router

router = APIRouter(prefix="/admin")

# Include order router
router.include_router(order_router)

@router.get("/users")
async def get_admin_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    email_verified: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc"),
    current_user = Depends(require_admin)
):
    """Get all users for admin management"""
    try:
        admin_manager = AdminManager()
        result = await admin_manager.get_users(
            page=page,
            limit=limit,
            role=role,
            is_active=is_active,
            email_verified=email_verified,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return success_response(
            data=result["users"],
            message="Users retrieved successfully",
            meta={
                "pagination": {
                    "current_page": page,
                    "per_page": limit,
                    "total": result["total"],
                    "total_pages": (result["total"] + limit - 1) // limit
                }
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Removed duplicate admin orders endpoints - using dedicated admin/order_router.py instead

# @router.get("/admin/orders/{order_id}")
# async def get_admin_order(
#     order_id: str,
#     current_user = Depends(require_admin)
# ):
# Commented out - using dedicated admin/order_router.py instead
#     """Get specific order for admin"""
#     try:
#         admin_manager = AdminManager()
#         order = await admin_manager.get_order_by_id(order_id)
#         if not order:
#             raise HTTPException(status_code=404, detail="Order not found")
#         return success_response(data=order, message="Order retrieved successfully")
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role_data: dict,
    current_user = Depends(require_admin)
):
    """Update user role (admin only)"""
    try:
        admin_manager = AdminManager()
        user = await admin_manager.update_user_role(user_id, role_data.get("role"))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return success_response(data=user, message="User role updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}")
async def get_admin_user(
    user_id: str,
    current_user = Depends(require_admin)
):
    """Get specific user for admin"""
    try:
        admin_manager = AdminManager()
        user = await admin_manager.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return success_response(data=user, message="User retrieved successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users")
async def create_admin_user(
    user_data: UserCreateRequest,
    current_user = Depends(require_admin)
):
    """Create a new user (admin only)"""
    try:
        admin_manager = AdminManager()
        user = await admin_manager.create_user(user_data)
        return success_response(data=user, message="User created successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/users/{user_id}")
async def update_admin_user(
    user_id: str,
    user_data: UserUpdateRequest,
    current_user = Depends(require_admin)
):
    """Update user information (admin only)"""
    try:
        admin_manager = AdminManager()
        user = await admin_manager.update_user(user_id, user_data)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return success_response(data=user, message="User updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/users/{user_id}")
async def delete_admin_user(
    user_id: str,
    current_user = Depends(require_admin)
):
    """Delete/Deactivate a user (admin only)"""
    try:
        admin_manager = AdminManager()
        success = await admin_manager.delete_user(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        return success_response(data={"deleted": True}, message="User deactivated successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/users/{user_id}/status")
async def toggle_user_status(
    user_id: str,
    status_data: dict,
    current_user = Depends(require_admin)
):
    """Toggle user active status (admin only)"""
    try:
        admin_manager = AdminManager()
        user = await admin_manager.update_user_status(user_id, status_data.get("is_active"))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return success_response(data=user, message="User status updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/statistics/overview")
async def get_user_statistics(
    current_user = Depends(require_admin)
):
    """Get user statistics for admin dashboard"""
    try:
        admin_manager = AdminManager()
        stats = await admin_manager.get_user_statistics()
        return success_response(data=stats, message="User statistics retrieved successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/products")
async def get_admin_products(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category_id: Optional[str] = Query(None),
    in_stock: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    featured: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc"),
    current_user = Depends(require_admin)
):
    """Get all products for admin management"""
    try:
        result = await admin_product_manager.get_products(
            page=page,
            limit=limit,
            category_id=category_id,
            in_stock=in_stock,
            is_active=is_active,
            featured=featured,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return success_response(
            data=result["products"],
            message="Products retrieved successfully",
            meta={
                "pagination": {
                    "current_page": page,
                    "per_page": limit,
                    "total": result["total"],
                    "total_pages": (result["total"] + limit - 1) // limit
                }
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/products/{product_id}")
async def get_admin_product(
    product_id: str,
    current_user = Depends(require_admin)
):
    """Get specific product for admin"""
    try:
        product = await admin_product_manager.get_product_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return success_response(data=product, message="Product retrieved successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/products")
async def create_admin_product(
    product_data: ProductCreateRequest,
    current_user = Depends(require_admin)
):
    """Create a new product (admin only)"""
    try:
        product = await admin_product_manager.create_product(product_data)
        return success_response(data=product, message="Product created successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/products/{product_id}")
async def update_admin_product(
    product_id: str,
    product_data: ProductUpdateRequest,
    current_user = Depends(require_admin)
):
    """Update a product (admin only)"""
    try:
        product = await admin_product_manager.update_product(product_id, product_data)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return success_response(data=product, message="Product updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/products/{product_id}")
async def delete_admin_product(
    product_id: str,
    current_user = Depends(require_admin)
):
    """Delete a product (admin only)"""
    try:
        success = await admin_product_manager.delete_product(product_id)
        if not success:
            raise HTTPException(status_code=404, detail="Product not found")
        return success_response(data={"deleted": True}, message="Product deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))