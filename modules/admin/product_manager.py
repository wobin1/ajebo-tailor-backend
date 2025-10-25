"""
Admin product manager for handling product CRUD operations
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncpg

from .models import AdminProductResponse, ProductCreateRequest, ProductUpdateRequest
from shared.db import db_manager


class AdminProductManager:
    def __init__(self):
        pass

    async def get_products(
        self,
        page: int = 1,
        limit: int = 20,
        category_id: Optional[str] = None,
        in_stock: Optional[bool] = None,
        is_active: Optional[bool] = None,
        featured: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Get all products for admin management with filtering"""
        try:
            async with db_manager.get_connection() as conn:
                # Build WHERE conditions
                where_conditions = []
                params = []
                param_count = 1

                if category_id:
                    where_conditions.append(f"p.category_id = ${param_count}")
                    params.append(category_id)
                    param_count += 1

                if in_stock is not None:
                    if in_stock:
                        where_conditions.append(f"p.stock_quantity > 0")
                    else:
                        where_conditions.append(f"p.stock_quantity = 0")

                if is_active is not None:
                    where_conditions.append(f"p.is_active = ${param_count}")
                    params.append(is_active)
                    param_count += 1

                if featured is not None:
                    where_conditions.append(f"p.featured = ${param_count}")
                    params.append(featured)
                    param_count += 1

                if search:
                    where_conditions.append(f"(p.name ILIKE ${param_count} OR p.description ILIKE ${param_count + 1} OR ${param_count + 2} = ANY(p.tags))")
                    search_term = f"%{search}%"
                    params.extend([search_term, search_term, search])
                    param_count += 3

                # Build WHERE clause
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)

                # Build ORDER BY clause
                valid_sort_fields = ["name", "price", "stock_quantity", "created_at", "updated_at"]
                if sort_by not in valid_sort_fields:
                    sort_by = "created_at"
                
                sort_order = "ASC" if sort_order.upper() == "ASC" else "DESC"
                order_clause = f"ORDER BY p.{sort_by} {sort_order}"

                # Get total count
                count_query = f"""
                    SELECT COUNT(*)
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                    LEFT JOIN categories sc ON p.subcategory_id = sc.id
                    {where_clause}
                """
                
                total_result = await conn.fetchrow(count_query, *params)
                total = total_result[0] if total_result else 0

                # Get products with pagination
                offset = (page - 1) * limit
                products_query = f"""
                    SELECT 
                        p.id, p.name, p.description, p.price, p.original_price,
                        p.sku, p.stock_quantity, p.category_id, p.subcategory_id,
                        p.colors, p.sizes, p.tags, p.images, p.featured, p.is_active,
                        p.created_at, p.updated_at,
                        c.name as category_name,
                        sc.name as subcategory_name
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                    LEFT JOIN categories sc ON p.subcategory_id = sc.id
                    {where_clause}
                    {order_clause}
                    LIMIT ${param_count} OFFSET ${param_count + 1}
                """
                
                params.extend([limit, offset])
                products_result = await conn.fetch(products_query, *params)

                # Convert to proper format
                products = []
                for row in products_result:
                    product = dict(row)
                    
                    # Convert decimal to float
                    if product.get('price'):
                        product['price'] = float(product['price'])
                    if product.get('original_price'):
                        product['original_price'] = float(product['original_price'])
                    
                    # Convert datetime objects to ISO strings
                    if product.get('created_at'):
                        product['created_at'] = product['created_at'].isoformat()
                    if product.get('updated_at'):
                        product['updated_at'] = product['updated_at'].isoformat()
                    
                    # Ensure arrays are not None
                    product['colors'] = product['colors'] or []
                    product['sizes'] = product['sizes'] or []
                    product['tags'] = product['tags'] or []
                    product['images'] = product['images'] or []
                    
                    products.append(product)

                return {
                    "products": products,
                    "total": total
                }

        except Exception as e:
            raise Exception(f"Failed to get products: {str(e)}")

    async def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific product by ID"""
        try:
            async with db_manager.get_connection() as conn:
                query = """
                    SELECT 
                        p.id, p.name, p.description, p.price, p.original_price,
                        p.sku, p.stock_quantity, p.category_id, p.subcategory_id,
                        p.colors, p.sizes, p.tags, p.images, p.featured, p.is_active,
                        p.created_at, p.updated_at,
                        c.name as category_name,
                        sc.name as subcategory_name
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                    LEFT JOIN categories sc ON p.subcategory_id = sc.id
                    WHERE p.id = $1
                """
                
                result = await conn.fetchrow(query, product_id)
                if not result:
                    return None

                # Convert to proper format
                product = dict(result)
                
                # Convert decimal to float
                if product.get('price'):
                    product['price'] = float(product['price'])
                if product.get('original_price'):
                    product['original_price'] = float(product['original_price'])
                
                # Convert datetime objects to ISO strings
                if product.get('created_at'):
                    product['created_at'] = product['created_at'].isoformat()
                if product.get('updated_at'):
                    product['updated_at'] = product['updated_at'].isoformat()
                
                # Ensure arrays are not None
                product['colors'] = product['colors'] or []
                product['sizes'] = product['sizes'] or []
                product['tags'] = product['tags'] or []
                product['images'] = product['images'] or []
                
                return product

        except Exception as e:
            raise Exception(f"Failed to get product: {str(e)}")

    async def create_product(self, product_data: ProductCreateRequest) -> Dict[str, Any]:
        """Create a new product"""
        try:
            async with db_manager.get_connection() as conn:
                # Generate slug from name
                import re
                slug = re.sub(r'[^a-zA-Z0-9]+', '-', product_data.name.lower()).strip('-')
                
                # Check if slug already exists and make it unique
                existing = await conn.fetchrow("SELECT id FROM products WHERE slug = $1", slug)
                counter = 1
                original_slug = slug
                while existing:
                    slug = f"{original_slug}-{counter}"
                    existing = await conn.fetchrow("SELECT id FROM products WHERE slug = $1", slug)
                    counter += 1

                query = """
                    INSERT INTO products (
                        name, slug, description, price, original_price, sku,
                        stock_quantity, category_id, subcategory_id, colors,
                        sizes, tags, images, featured, is_active
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
                    ) RETURNING *
                """
                
                result = await conn.fetchrow(
                    query,
                    product_data.name,
                    slug,
                    product_data.description,
                    product_data.price,
                    product_data.original_price,
                    product_data.sku,
                    product_data.stock_quantity,
                    product_data.category_id if product_data.category_id else None,
                    product_data.subcategory_id if product_data.subcategory_id else None,
                    product_data.colors,
                    product_data.sizes,
                    product_data.tags,
                    product_data.images,
                    product_data.featured,
                    product_data.is_active
                )

                # Convert to proper format
                product = dict(result)
                
                # Convert decimal to float
                if product.get('price'):
                    product['price'] = float(product['price'])
                if product.get('original_price'):
                    product['original_price'] = float(product['original_price'])
                
                # Convert datetime objects to ISO strings
                if product.get('created_at'):
                    product['created_at'] = product['created_at'].isoformat()
                if product.get('updated_at'):
                    product['updated_at'] = product['updated_at'].isoformat()
                
                return product

        except Exception as e:
            raise Exception(f"Failed to create product: {str(e)}")

    async def update_product(self, product_id: str, product_data: ProductUpdateRequest) -> Optional[Dict[str, Any]]:
        """Update a product"""
        try:
            async with db_manager.get_connection() as conn:
                # Build update fields
                update_fields = []
                params = []
                param_count = 1

                if product_data.name is not None:
                    update_fields.append(f"name = ${param_count}")
                    params.append(product_data.name)
                    param_count += 1
                    
                    # Update slug if name changed
                    import re
                    slug = re.sub(r'[^a-zA-Z0-9]+', '-', product_data.name.lower()).strip('-')
                    update_fields.append(f"slug = ${param_count}")
                    params.append(slug)
                    param_count += 1

                if product_data.description is not None:
                    update_fields.append(f"description = ${param_count}")
                    params.append(product_data.description)
                    param_count += 1

                if product_data.price is not None:
                    update_fields.append(f"price = ${param_count}")
                    params.append(product_data.price)
                    param_count += 1

                if product_data.original_price is not None:
                    update_fields.append(f"original_price = ${param_count}")
                    params.append(product_data.original_price)
                    param_count += 1

                if product_data.sku is not None:
                    update_fields.append(f"sku = ${param_count}")
                    params.append(product_data.sku)
                    param_count += 1

                if product_data.stock_quantity is not None:
                    update_fields.append(f"stock_quantity = ${param_count}")
                    params.append(product_data.stock_quantity)
                    param_count += 1

                if product_data.category_id is not None:
                    update_fields.append(f"category_id = ${param_count}")
                    params.append(product_data.category_id if product_data.category_id else None)
                    param_count += 1

                if product_data.subcategory_id is not None:
                    update_fields.append(f"subcategory_id = ${param_count}")
                    params.append(product_data.subcategory_id if product_data.subcategory_id else None)
                    param_count += 1

                if product_data.colors is not None:
                    update_fields.append(f"colors = ${param_count}")
                    params.append(product_data.colors)
                    param_count += 1

                if product_data.sizes is not None:
                    update_fields.append(f"sizes = ${param_count}")
                    params.append(product_data.sizes)
                    param_count += 1

                if product_data.tags is not None:
                    update_fields.append(f"tags = ${param_count}")
                    params.append(product_data.tags)
                    param_count += 1

                if product_data.images is not None:
                    update_fields.append(f"images = ${param_count}")
                    params.append(product_data.images)
                    param_count += 1

                if product_data.featured is not None:
                    update_fields.append(f"featured = ${param_count}")
                    params.append(product_data.featured)
                    param_count += 1

                if product_data.is_active is not None:
                    update_fields.append(f"is_active = ${param_count}")
                    params.append(product_data.is_active)
                    param_count += 1

                if not update_fields:
                    return None

                # Add updated_at
                update_fields.append(f"updated_at = NOW()")

                query = f"""
                    UPDATE products 
                    SET {', '.join(update_fields)}
                    WHERE id = ${param_count}
                    RETURNING *
                """
                params.append(product_id)

                result = await conn.fetchrow(query, *params)
                if not result:
                    return None

                # Convert to proper format
                product = dict(result)
                
                # Convert decimal to float
                if product.get('price'):
                    product['price'] = float(product['price'])
                if product.get('original_price'):
                    product['original_price'] = float(product['original_price'])
                
                # Convert datetime objects to ISO strings
                if product.get('created_at'):
                    product['created_at'] = product['created_at'].isoformat()
                if product.get('updated_at'):
                    product['updated_at'] = product['updated_at'].isoformat()
                
                return product

        except Exception as e:
            raise Exception(f"Failed to update product: {str(e)}")

    async def delete_product(self, product_id: str) -> bool:
        """Delete a product"""
        try:
            async with db_manager.get_connection() as conn:
                result = await conn.execute("DELETE FROM products WHERE id = $1", product_id)
                return result == "DELETE 1"

        except Exception as e:
            raise Exception(f"Failed to delete product: {str(e)}")


# Create global instance
admin_product_manager = AdminProductManager()
