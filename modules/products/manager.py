import logging
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from shared.db import db_manager
from shared.utils import slugify, generate_sku, PaginationParams
from shared.response import NotFoundException, ValidationException, ConflictException
from .models import (
    ProductResponse, ProductCreate, ProductUpdate, ProductFilters,
    CategoryResponse, CategoryCreate, CategoryUpdate
)

logger = logging.getLogger(__name__)

class ProductManager:
    """Product management business logic"""
    
    async def create_product(self, product_data: ProductCreate) -> ProductResponse:
        """Create a new product"""
        try:
            # Generate slug from name
            slug = slugify(product_data.name)
            
            # Check if slug already exists
            existing_product = await db_manager.fetch_one(
                "SELECT id FROM products WHERE slug = $1",
                slug
            )
            
            if existing_product:
                # Make slug unique by appending a number
                counter = 1
                while existing_product:
                    new_slug = f"{slug}-{counter}"
                    existing_product = await db_manager.fetch_one(
                        "SELECT id FROM products WHERE slug = $1",
                        new_slug
                    )
                    counter += 1
                slug = new_slug
            
            # Generate SKU if not provided
            sku = product_data.sku
            if not sku:
                category_name = "PROD"  # Default category
                if product_data.category_id:
                    category_data = await db_manager.fetch_one(
                        "SELECT name FROM categories WHERE id = $1",
                        product_data.category_id
                    )
                    if category_data:
                        category_name = category_data["name"]
                
                sku = generate_sku(category_name, product_data.name)
            
            # Set in_stock based on stock_quantity
            in_stock = product_data.stock_quantity > 0
            
            # Create product
            product_id = await db_manager.fetch_val(
                """
                INSERT INTO products (
                    name, slug, description, price, original_price, category_id, subcategory_id,
                    images, sizes, colors, tags, in_stock, stock_quantity, featured, sku,
                    weight, dimensions, meta_title, meta_description
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                RETURNING id
                """,
                product_data.name, slug, product_data.description, product_data.price,
                product_data.original_price, product_data.category_id, product_data.subcategory_id,
                product_data.images, product_data.sizes, product_data.colors, product_data.tags,
                in_stock, product_data.stock_quantity, product_data.featured, sku,
                product_data.weight, product_data.dimensions, product_data.meta_title,
                product_data.meta_description
            )
            
            # Return created product
            product = await self.get_product_by_id(str(product_id))
            logger.info(f"Product created: {product_id}")
            
            return product
            
        except Exception as e:
            logger.error(f"Failed to create product: {e}")
            raise
    
    async def get_products(
        self, 
        filters: ProductFilters = None, 
        pagination: PaginationParams = None
    ) -> Tuple[List[ProductResponse], int]:
        """Get products with filtering and pagination"""
        try:
            # Build WHERE clause
            where_conditions = ["p.is_active = true"]
            params = []
            param_count = 1
            
            if filters:
                if filters.category:
                    where_conditions.append(f"c.slug = ${param_count}")
                    params.append(filters.category)
                    param_count += 1
                
                if filters.subcategory:
                    where_conditions.append(f"sc.slug = ${param_count}")
                    params.append(filters.subcategory)
                    param_count += 1
                
                if filters.search:
                    where_conditions.append(f"(p.name ILIKE ${param_count} OR p.description ILIKE ${param_count + 1} OR ${param_count + 2} = ANY(p.tags))")
                    search_term = f"%{filters.search}%"
                    params.extend([search_term, search_term, filters.search])
                    param_count += 3
                
                if filters.min_price is not None:
                    where_conditions.append(f"p.price >= ${param_count}")
                    params.append(filters.min_price)
                    param_count += 1
                
                if filters.max_price is not None:
                    where_conditions.append(f"p.price <= ${param_count}")
                    params.append(filters.max_price)
                    param_count += 1
                
                if filters.colors:
                    where_conditions.append(f"p.colors && ${param_count}")
                    params.append(filters.colors)
                    param_count += 1
                
                if filters.sizes:
                    where_conditions.append(f"p.sizes && ${param_count}")
                    params.append(filters.sizes)
                    param_count += 1
                
                if filters.tags:
                    where_conditions.append(f"p.tags && ${param_count}")
                    params.append(filters.tags)
                    param_count += 1
                
                if filters.featured is not None:
                    where_conditions.append(f"p.featured = ${param_count}")
                    params.append(filters.featured)
                    param_count += 1
                
                if filters.in_stock is not None:
                    where_conditions.append(f"p.in_stock = ${param_count}")
                    params.append(filters.in_stock)
                    param_count += 1
            
            where_clause = " AND ".join(where_conditions)
            
            # Build ORDER BY clause
            sort_by = "p.created_at"
            sort_order = "DESC"
            
            if filters:
                if filters.sort_by == "name":
                    sort_by = "p.name"
                elif filters.sort_by == "price":
                    sort_by = "p.price"
                elif filters.sort_by == "updated_at":
                    sort_by = "p.updated_at"
                elif filters.sort_by == "featured":
                    sort_by = "p.featured"
                
                if filters.sort_order == "asc":
                    sort_order = "ASC"
            
            # Get total count
            count_query = f"""
                SELECT COUNT(*)
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                LEFT JOIN categories sc ON p.subcategory_id = sc.id
                WHERE {where_clause}
            """
            
            total = await db_manager.fetch_val(count_query, *params)
            
            # Get products
            limit_clause = ""
            if pagination:
                limit_clause = f"LIMIT {pagination.get_limit()} OFFSET {pagination.get_offset()}"
            
            query = f"""
                SELECT p.id, p.name, p.slug, p.description, p.price, p.original_price,
                       p.category_id, p.subcategory_id, p.images, p.sizes, p.colors, p.tags,
                       p.in_stock, p.stock_quantity, p.featured, p.is_active, p.sku,
                       p.weight, p.dimensions, p.meta_title, p.meta_description,
                       p.created_at, p.updated_at
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                LEFT JOIN categories sc ON p.subcategory_id = sc.id
                WHERE {where_clause}
                ORDER BY {sort_by} {sort_order}
                {limit_clause}
            """
            
            products_data = await db_manager.fetch_all(query, *params)
            
            products = [
                ProductResponse(
                    id=str(product["id"]),
                    name=product["name"],
                    slug=product["slug"],
                    description=product["description"],
                    price=product["price"],
                    original_price=product["original_price"],
                    category_id=str(product["category_id"]) if product["category_id"] else None,
                    subcategory_id=str(product["subcategory_id"]) if product["subcategory_id"] else None,
                    images=product["images"] or [],
                    sizes=product["sizes"] or [],
                    colors=product["colors"] or [],
                    tags=product["tags"] or [],
                    in_stock=product["in_stock"],
                    stock_quantity=product["stock_quantity"],
                    featured=product["featured"],
                    is_active=product["is_active"],
                    sku=product["sku"],
                    weight=product["weight"],
                    dimensions=product["dimensions"],
                    meta_title=product["meta_title"],
                    meta_description=product["meta_description"],
                    created_at=product["created_at"],
                    updated_at=product["updated_at"]
                )
                for product in products_data
            ]
            
            return products, total
            
        except Exception as e:
            logger.error(f"Failed to get products: {e}")
            raise
    
    async def get_product_by_id(self, product_id: str) -> Optional[ProductResponse]:
        """Get product by ID"""
        try:
            product_data = await db_manager.fetch_one(
                """
                SELECT id, name, slug, description, price, original_price,
                       category_id, subcategory_id, images, sizes, colors, tags,
                       in_stock, stock_quantity, featured, is_active, sku,
                       weight, dimensions, meta_title, meta_description,
                       created_at, updated_at
                FROM products 
                WHERE id = $1 AND is_active = true
                """,
                product_id
            )
            
            if not product_data:
                return None
            
            return ProductResponse(
                id=str(product_data["id"]),
                name=product_data["name"],
                slug=product_data["slug"],
                description=product_data["description"],
                price=product_data["price"],
                original_price=product_data["original_price"],
                category_id=str(product_data["category_id"]) if product_data["category_id"] else None,
                subcategory_id=str(product_data["subcategory_id"]) if product_data["subcategory_id"] else None,
                images=product_data["images"] or [],
                sizes=product_data["sizes"] or [],
                colors=product_data["colors"] or [],
                tags=product_data["tags"] or [],
                in_stock=product_data["in_stock"],
                stock_quantity=product_data["stock_quantity"],
                featured=product_data["featured"],
                is_active=product_data["is_active"],
                sku=product_data["sku"],
                weight=product_data["weight"],
                dimensions=product_data["dimensions"],
                meta_title=product_data["meta_title"],
                meta_description=product_data["meta_description"],
                created_at=product_data["created_at"],
                updated_at=product_data["updated_at"]
            )
            
        except Exception as e:
            logger.error(f"Failed to get product by ID: {e}")
            return None
    
    async def get_product_by_slug(self, slug: str) -> Optional[ProductResponse]:
        """Get product by slug"""
        try:
            product_data = await db_manager.fetch_one(
                """
                SELECT id, name, slug, description, price, original_price,
                       category_id, subcategory_id, images, sizes, colors, tags,
                       in_stock, stock_quantity, featured, is_active, sku,
                       weight, dimensions, meta_title, meta_description,
                       created_at, updated_at
                FROM products 
                WHERE slug = $1 AND is_active = true
                """,
                slug
            )
            
            if not product_data:
                return None
            
            return ProductResponse(
                id=str(product_data["id"]),
                name=product_data["name"],
                slug=product_data["slug"],
                description=product_data["description"],
                price=product_data["price"],
                original_price=product_data["original_price"],
                category_id=str(product_data["category_id"]) if product_data["category_id"] else None,
                subcategory_id=str(product_data["subcategory_id"]) if product_data["subcategory_id"] else None,
                images=product_data["images"] or [],
                sizes=product_data["sizes"] or [],
                colors=product_data["colors"] or [],
                tags=product_data["tags"] or [],
                in_stock=product_data["in_stock"],
                stock_quantity=product_data["stock_quantity"],
                featured=product_data["featured"],
                is_active=product_data["is_active"],
                sku=product_data["sku"],
                weight=product_data["weight"],
                dimensions=product_data["dimensions"],
                meta_title=product_data["meta_title"],
                meta_description=product_data["meta_description"],
                created_at=product_data["created_at"],
                updated_at=product_data["updated_at"]
            )
            
        except Exception as e:
            logger.error(f"Failed to get product by slug: {e}")
            return None
    
    # Category management
    async def create_category(self, category_data: CategoryCreate) -> CategoryResponse:
        """Create a new category"""
        try:
            # Generate slug from name
            slug = slugify(category_data.name)
            
            # Check if slug already exists
            existing_category = await db_manager.fetch_one(
                "SELECT id FROM categories WHERE slug = $1",
                slug
            )
            
            if existing_category:
                raise ConflictException("Category with this name already exists")
            
            # Create category
            category_id = await db_manager.fetch_val(
                """
                INSERT INTO categories (name, slug, description, image, parent_id, sort_order)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                category_data.name, slug, category_data.description,
                category_data.image, category_data.parent_id, category_data.sort_order
            )
            
            # Return created category
            category = await self.get_category_by_id(str(category_id))
            logger.info(f"Category created: {category_id}")
            
            return category
            
        except Exception as e:
            logger.error(f"Failed to create category: {e}")
            raise
    
    async def get_categories(self) -> List[CategoryResponse]:
        """Get all active categories"""
        try:
            categories_data = await db_manager.fetch_all(
                """
                SELECT id, name, slug, description, image, parent_id, is_active,
                       sort_order, created_at, updated_at
                FROM categories 
                WHERE is_active = true
                ORDER BY sort_order ASC, name ASC
                """
            )
            
            return [
                CategoryResponse(
                    id=str(cat["id"]),
                    name=cat["name"],
                    slug=cat["slug"],
                    description=cat["description"],
                    image=cat["image"],
                    parent_id=str(cat["parent_id"]) if cat["parent_id"] else None,
                    is_active=cat["is_active"],
                    sort_order=cat["sort_order"],
                    created_at=cat["created_at"],
                    updated_at=cat["updated_at"]
                )
                for cat in categories_data
            ]
            
        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
            return []
    
    async def get_category_by_id(self, category_id: str) -> Optional[CategoryResponse]:
        """Get category by ID"""
        try:
            category_data = await db_manager.fetch_one(
                """
                SELECT id, name, slug, description, image, parent_id, is_active,
                       sort_order, created_at, updated_at
                FROM categories 
                WHERE id = $1 AND is_active = true
                """,
                category_id
            )
            
            if not category_data:
                return None
            
            return CategoryResponse(
                id=str(category_data["id"]),
                name=category_data["name"],
                slug=category_data["slug"],
                description=category_data["description"],
                image=category_data["image"],
                parent_id=str(category_data["parent_id"]) if category_data["parent_id"] else None,
                is_active=category_data["is_active"],
                sort_order=category_data["sort_order"],
                created_at=category_data["created_at"],
                updated_at=category_data["updated_at"]
            )
            
        except Exception as e:
            logger.error(f"Failed to get category by ID: {e}")
            return None
    
    async def get_category_by_slug(self, slug: str) -> Optional[CategoryResponse]:
        """Get category by slug"""
        try:
            category_data = await db_manager.fetch_one(
                """
                SELECT id, name, slug, description, image, parent_id, is_active,
                       sort_order, created_at, updated_at
                FROM categories 
                WHERE slug = $1 AND is_active = true
                """,
                slug
            )
            
            if not category_data:
                return None
            
            return CategoryResponse(
                id=str(category_data["id"]),
                name=category_data["name"],
                slug=category_data["slug"],
                description=category_data["description"],
                image=category_data["image"],
                parent_id=str(category_data["parent_id"]) if category_data["parent_id"] else None,
                is_active=category_data["is_active"],
                sort_order=category_data["sort_order"],
                created_at=category_data["created_at"],
                updated_at=category_data["updated_at"]
            )
            
        except Exception as e:
            logger.error(f"Failed to get category by slug: {e}")
            return None

# Global product manager instance
product_manager = ProductManager()