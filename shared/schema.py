import asyncio
import logging
from pathlib import Path
from .db import db_manager

logger = logging.getLogger(__name__)

async def initialize_database():
    """Initialize database with schema and seed data"""
    try:
        # Read schema file
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Execute schema
        async with db_manager.get_connection() as conn:
            await conn.execute(schema_sql)
        
        logger.info("Database schema initialized successfully")
        
        # Run seed data if needed
        await seed_initial_data()
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

async def seed_initial_data():
    """Seed initial data into the database"""
    try:
        # Check if we already have data
        user_count = await db_manager.fetch_val("SELECT COUNT(*) FROM users")
        if user_count > 0:
            logger.info("Database already has data, skipping seed")
            return
        
        # Seed categories
        categories_data = [
            ("Men's Clothing", "mens-clothing", "Stylish clothing for men", None),
            ("Women's Clothing", "womens-clothing", "Elegant clothing for women", None),
            ("Accessories", "accessories", "Fashion accessories", None),
            ("Suits", "suits", "Professional suits", None),
            ("Casual Wear", "casual-wear", "Comfortable casual clothing", None),
        ]
        
        category_ids = {}
        for name, slug, description, parent_id in categories_data:
            category_id = await db_manager.fetch_val(
                """
                INSERT INTO categories (name, slug, description, parent_id)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                name, slug, description, parent_id
            )
            category_ids[slug] = category_id
        
        # Seed admin user
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        admin_password = pwd_context.hash("admin123")
        await db_manager.execute_query(
            """
            INSERT INTO users (email, name, password_hash, role, email_verified)
            VALUES ($1, $2, $3, $4, $5)
            """,
            "admin@ajebotailor.com", "Admin User", admin_password, "admin", True
        )
        
        # Seed sample products
        sample_products = [
            {
                "name": "Classic Black Suit",
                "slug": "classic-black-suit",
                "description": "Elegant black suit perfect for formal occasions",
                "price": 299.99,
                "original_price": 399.99,
                "category_id": category_ids["suits"],
                "images": ["/images/products/black-suit-1.jpg", "/images/products/black-suit-2.jpg"],
                "sizes": ["S", "M", "L", "XL", "XXL"],
                "colors": ["Black", "Navy"],
                "tags": ["formal", "suit", "business"],
                "featured": True,
                "stock_quantity": 50,
                "sku": "BS001"
            },
            {
                "name": "Casual Cotton Shirt",
                "slug": "casual-cotton-shirt",
                "description": "Comfortable cotton shirt for everyday wear",
                "price": 49.99,
                "category_id": category_ids["casual-wear"],
                "images": ["/images/products/cotton-shirt-1.jpg"],
                "sizes": ["S", "M", "L", "XL"],
                "colors": ["White", "Blue", "Gray"],
                "tags": ["casual", "shirt", "cotton"],
                "featured": False,
                "stock_quantity": 100,
                "sku": "CS001"
            },
            {
                "name": "Designer Handbag",
                "slug": "designer-handbag",
                "description": "Luxury designer handbag made from premium leather",
                "price": 199.99,
                "category_id": category_ids["accessories"],
                "images": ["/images/products/handbag-1.jpg", "/images/products/handbag-2.jpg"],
                "sizes": ["One Size"],
                "colors": ["Black", "Brown", "Red"],
                "tags": ["accessories", "handbag", "leather"],
                "featured": True,
                "stock_quantity": 25,
                "sku": "HB001"
            }
        ]
        
        for product in sample_products:
            await db_manager.execute_query(
                """
                INSERT INTO products (
                    name, slug, description, price, original_price, category_id,
                    images, sizes, colors, tags, featured, stock_quantity, sku, in_stock
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                product["name"], product["slug"], product["description"],
                product["price"], product.get("original_price"), product["category_id"],
                product["images"], product["sizes"], product["colors"], product["tags"],
                product["featured"], product["stock_quantity"], product["sku"], True
            )
        
        logger.info("Initial seed data inserted successfully")
        
    except Exception as e:
        logger.error(f"Failed to seed initial data: {e}")
        raise

async def apply_migrations():
    """Apply pending database migrations"""
    try:
        async with db_manager.get_connection() as conn:
            # Migration 1: Check if customizations column exists in cart_items
            column_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'cart_items' 
                    AND column_name = 'customizations'
                )
                """
            )
            
            if not column_exists:
                await conn.execute("ALTER TABLE cart_items ADD COLUMN customizations JSONB")
                logger.info("Added customizations column to cart_items table")
            else:
                logger.info("Customizations column already exists in cart_items table")
            
            # Migration 2: Check if priority column exists in orders
            priority_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'orders' 
                    AND column_name = 'priority'
                )
                """
            )
            
            if not priority_exists:
                # Read and execute the priority migration SQL
                migration_path = Path(__file__).parent / "migrations" / "add_priority_to_orders.sql"
                with open(migration_path, 'r') as f:
                    migration_sql = f.read()
                
                await conn.execute(migration_sql)
                logger.info("Added priority column to orders table")
            else:
                logger.info("Priority column already exists in orders table")
                
    except Exception as e:
        logger.error(f"Failed to apply migrations: {e}")
        raise

async def drop_all_tables():
    """Drop all tables - use with caution!"""
    try:
        drop_sql = """
        DROP TABLE IF EXISTS user_sessions CASCADE;
        DROP TABLE IF EXISTS coupons CASCADE;
        DROP TABLE IF EXISTS wishlists CASCADE;
        DROP TABLE IF EXISTS product_reviews CASCADE;
        DROP TABLE IF EXISTS cart_items CASCADE;
        DROP TABLE IF EXISTS order_items CASCADE;
        DROP TABLE IF EXISTS orders CASCADE;
        DROP TABLE IF EXISTS addresses CASCADE;
        DROP TABLE IF EXISTS products CASCADE;
        DROP TABLE IF EXISTS categories CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
        DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
        """
        
        async with db_manager.get_connection() as conn:
            await conn.execute(drop_sql)
        
        logger.info("All tables dropped successfully")
        
    except Exception as e:
        logger.error(f"Failed to drop tables: {e}")
        raise

if __name__ == "__main__":
    # For running schema initialization directly
    async def main():
        await db_manager.connect()
        await initialize_database()
        await db_manager.disconnect()
    
    asyncio.run(main())