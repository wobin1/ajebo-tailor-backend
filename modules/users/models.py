from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    avatar: Optional[str] = None

class AddressCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    company: Optional[str] = Field(None, max_length=255)
    address1: str = Field(..., min_length=1, max_length=255)
    address2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    zip_code: str = Field(..., min_length=1, max_length=20)
    country: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_default: Optional[bool] = False
    address_type: str = Field(default="shipping", pattern="^(shipping|billing|both)$")

class AddressUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    company: Optional[str] = Field(None, max_length=255)
    address1: Optional[str] = Field(None, min_length=1, max_length=255)
    address2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=1, max_length=100)
    zip_code: Optional[str] = Field(None, min_length=1, max_length=20)
    country: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_default: Optional[bool] = None
    address_type: Optional[str] = Field(None, pattern="^(shipping|billing|both)$")

class AddressResponse(BaseModel):
    id: str
    user_id: str
    first_name: str
    last_name: str
    company: Optional[str]
    address1: str
    address2: Optional[str]
    city: str
    state: str
    zip_code: str
    country: str
    phone: Optional[str]
    is_default: bool
    address_type: str
    created_at: datetime
    updated_at: datetime