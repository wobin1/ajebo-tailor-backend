import logging
import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import redis.asyncio as redis

from shared.db import db_manager
from shared.schema import initialize_database, apply_migrations
from shared.response import error_response
from modules.auth.router import router as auth_router
from modules.users.router import router as users_router
from modules.products.router import router as products_router, categories_router
from modules.orders.router import router as orders_router
from modules.stats.router import router as stats_router
from modules.admin.router import router as admin_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Environment variables
CORS_ORIGINS = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000").split(",")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Rate limiting setup
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Ajebo Tailor Backend API...")
    
    try:
        # Initialize database connection
        await db_manager.connect()
        logger.info("Database connection established")
        
        # Initialize database schema
        await initialize_database()
        logger.info("Database schema initialized")
        
        # Apply pending migrations
        await apply_migrations()
        logger.info("Database migrations applied")
        
        # Test Redis connection for rate limiting
        try:
            redis_client = redis.from_url(REDIS_URL)
            await redis_client.ping()
            await redis_client.close()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Rate limiting will use in-memory storage.")
        
        logger.info("Application startup completed successfully")
        
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Ajebo Tailor Backend API...")
    try:
        await db_manager.disconnect()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Create FastAPI application
app = FastAPI(
    title="Ajebo Tailor Backend API",
    description="A comprehensive e-commerce backend API for custom tailoring services",
    version="1.0.0",
    docs_url="/docs" if ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if ENVIRONMENT == "development" else None,
    lifespan=lifespan
)

# Add rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add trusted host middleware for production
if ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["ajebo-tailor.com", "*.ajebo-tailor.com", "api.ajebo-tailor.com"]
    )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(exc.detail, exc.status_code)
        )
    
    # Don't expose internal errors in production
    if ENVIRONMENT == "production":
        return JSONResponse(
            status_code=500,
            content=error_response("Internal server error", 500)
        )
    else:
        return JSONResponse(
            status_code=500,
            content=error_response(f"Internal server error: {str(exc)}", 500)
        )

# Health check endpoint
@app.get("/health", tags=["Health"])
@limiter.limit("10/minute")
async def health_check(request: Request):
    """Health check endpoint"""
    try:
        # Check database connection
        await db_manager.health_check()
        
        return {
            "status": "healthy",
            "service": "Ajebo Tailor Backend API",
            "version": "1.0.0",
            "environment": ENVIRONMENT,
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "Ajebo Tailor Backend API",
                "version": "1.0.0",
                "environment": ENVIRONMENT,
                "database": "disconnected",
                "error": str(e)
            }
        )

# Root endpoint
@app.get("/", tags=["Root"])
@limiter.limit("30/minute")
async def root(request: Request):
    """Root endpoint with API information"""
    return {
        "message": "Welcome to Ajebo Tailor Backend API",
        "version": "1.0.0",
        "docs": "/docs" if ENVIRONMENT == "development" else "Documentation not available in production",
        "health": "/health"
    }

# API version prefix
API_V1_PREFIX = "/api/v1"

# Include routers
app.include_router(auth_router, prefix=API_V1_PREFIX, tags=["Authentication"])
app.include_router(users_router, prefix=API_V1_PREFIX, tags=["Users"])
app.include_router(products_router, prefix=API_V1_PREFIX, tags=["Products"])
app.include_router(categories_router, prefix=API_V1_PREFIX, tags=["Categories"])
app.include_router(orders_router, prefix=API_V1_PREFIX, tags=["Orders"])
app.include_router(stats_router, prefix=API_V1_PREFIX, tags=["Statistics"])
app.include_router(admin_router, prefix=API_V1_PREFIX, tags=["Admin"])

# Import and include cart router separately
from modules.orders.router import cart_router
app.include_router(cart_router, prefix=API_V1_PREFIX, tags=["Cart"])

# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    start_time = time.time()
    
    # Log request
    logger.info(f"{request.method} {request.url.path} - Client: {request.client.host}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )
    
    return response

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response

if __name__ == "__main__":
    import uvicorn
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=ENVIRONMENT == "development",
        log_level="info"
    )