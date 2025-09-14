import asyncpg
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from pydantic_settings import BaseSettings
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class DatabaseSettings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/ajebo_tailor")
    database_host: str = os.getenv("DATABASE_HOST", "localhost")
    database_port: int = int(os.getenv("DATABASE_PORT", "5432"))
    database_name: str = os.getenv("DATABASE_NAME", "ajebo_tailor")
    database_user: str = os.getenv("DATABASE_USER", "postgres")
    database_password: str = os.getenv("DATABASE_PASSWORD", "password")
    min_pool_size: int = 5
    max_pool_size: int = 20

db_settings = DatabaseSettings()

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        
    async def connect(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                host=db_settings.database_host,
                port=db_settings.database_port,
                user=db_settings.database_user,
                password=db_settings.database_password,
                database=db_settings.database_name,
                min_size=db_settings.min_pool_size,
                max_size=db_settings.max_pool_size,
                command_timeout=60
            )
            logger.info("Database connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database connection pool: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def execute_query(self, query: str, *args) -> str:
        """Execute a query that doesn't return data (INSERT, UPDATE, DELETE)"""
        async with self.get_connection() as conn:
            return await conn.execute(query, *args)
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch single row"""
        async with self.get_connection() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch multiple rows"""
        async with self.get_connection() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def fetch_val(self, query: str, *args) -> Any:
        """Fetch single value"""
        async with self.get_connection() as conn:
            return await conn.fetchval(query, *args)

# Global database manager instance
db_manager = DatabaseManager()

# Convenience functions
async def get_db_connection():
    """Get database connection - for dependency injection"""
    async with db_manager.get_connection() as conn:
        yield conn

def with_db_transaction(func):
    """Decorator to wrap function in database transaction"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with db_manager.get_connection() as conn:
            async with conn.transaction():
                return await func(conn, *args, **kwargs)
    return wrapper

# Database health check
async def check_database_health() -> bool:
    """Check if database is healthy"""
    try:
        result = await db_manager.fetch_val("SELECT 1")
        return result == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False