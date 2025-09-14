from typing import Any, Optional, Dict, List, Union
from pydantic import BaseModel
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

class APIResponse(BaseModel):
    """Standard API response format"""
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    meta: Optional[Dict[str, Any]] = None

class PaginatedResponse(BaseModel):
    """Paginated response format"""
    success: bool = True
    message: str = "Success"
    data: List[Any]
    meta: Dict[str, Any]  # Contains pagination info

class ErrorResponse(BaseModel):
    """Error response format"""
    success: bool = False
    message: str
    errors: List[str]
    error_code: Optional[str] = None

def success_response(
    data: Any = None,
    message: str = "Success",
    meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a success response"""
    return {
        "success": True,
        "message": message,
        "data": data,
        "meta": meta
    }

def error_response(
    message: str = "An error occurred",
    errors: Optional[List[str]] = None,
    error_code: Optional[str] = None,
    status_code: int = status.HTTP_400_BAD_REQUEST
) -> JSONResponse:
    """Create an error response"""
    response_data = {
        "success": False,
        "message": message,
        "errors": errors or [message],
        "error_code": error_code
    }
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )

def paginated_response(
    data: List[Any],
    total: int,
    page: int = 1,
    limit: int = 10,
    message: str = "Success"
) -> Dict[str, Any]:
    """Create a paginated response"""
    total_pages = (total + limit - 1) // limit  # Ceiling division
    
    return {
        "success": True,
        "message": message,
        "data": data,
        "meta": {
            "pagination": {
                "current_page": page,
                "per_page": limit,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    }

def validation_error_response(errors: List[str]) -> JSONResponse:
    """Create a validation error response"""
    return error_response(
        message="Validation failed",
        errors=errors,
        error_code="VALIDATION_ERROR",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )

def not_found_response(resource: str = "Resource") -> JSONResponse:
    """Create a not found error response"""
    return error_response(
        message=f"{resource} not found",
        errors=[f"{resource} not found"],
        error_code="NOT_FOUND",
        status_code=status.HTTP_404_NOT_FOUND
    )

def unauthorized_response(message: str = "Unauthorized") -> JSONResponse:
    """Create an unauthorized error response"""
    return error_response(
        message=message,
        errors=[message],
        error_code="UNAUTHORIZED",
        status_code=status.HTTP_401_UNAUTHORIZED
    )

def forbidden_response(message: str = "Forbidden") -> JSONResponse:
    """Create a forbidden error response"""
    return error_response(
        message=message,
        errors=[message],
        error_code="FORBIDDEN",
        status_code=status.HTTP_403_FORBIDDEN
    )

def internal_server_error_response(message: str = "Internal server error") -> JSONResponse:
    """Create an internal server error response"""
    logger.error(f"Internal server error: {message}")
    return error_response(
        message="Internal server error",
        errors=["An unexpected error occurred"],
        error_code="INTERNAL_SERVER_ERROR",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

# Custom exceptions
class APIException(HTTPException):
    """Base API exception"""
    def __init__(
        self,
        status_code: int,
        message: str,
        errors: Optional[List[str]] = None,
        error_code: Optional[str] = None
    ):
        self.message = message
        self.errors = errors or [message]
        self.error_code = error_code
        super().__init__(status_code=status_code, detail=message)

class ValidationException(APIException):
    """Validation exception"""
    def __init__(self, errors: List[str]):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Validation failed",
            errors=errors,
            error_code="VALIDATION_ERROR"
        )

class NotFoundException(APIException):
    """Not found exception"""
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"{resource} not found",
            errors=[f"{resource} not found"],
            error_code="NOT_FOUND"
        )

class UnauthorizedException(APIException):
    """Unauthorized exception"""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=message,
            errors=[message],
            error_code="UNAUTHORIZED"
        )

class ForbiddenException(APIException):
    """Forbidden exception"""
    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            message=message,
            errors=[message],
            error_code="FORBIDDEN"
        )

class ConflictException(APIException):
    """Conflict exception"""
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            message=message,
            errors=[message],
            error_code="CONFLICT"
        )

# Aliases for backward compatibility
ValidationError = ValidationException
NotFoundError = NotFoundException
ConflictError = ConflictException