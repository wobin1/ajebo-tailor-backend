import re
import secrets
import string
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from passlib.context import CryptContext
from jose import JWTError, jwt
import os
from dotenv import load_dotenv

load_dotenv()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-jwt-key-change-this-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4()), "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def generate_random_string(length: int = 32) -> str:
    """Generate a random string"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password: str) -> tuple[bool, list[str]]:
    """Validate password strength"""
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")
    
    return len(errors) == 0, errors

def slugify(text: str) -> str:
    """Convert text to URL-friendly slug"""
    # Convert to lowercase and replace spaces with hyphens
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')

def generate_order_number() -> str:
    """Generate unique order number"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(secrets.choice(string.digits) for _ in range(6))
    return f"ORD-{timestamp}-{random_part}"

def generate_sku(category: str, name: str) -> str:
    """Generate SKU for product"""
    category_code = category[:3].upper()
    name_code = ''.join([word[0].upper() for word in name.split()[:3]])
    random_part = ''.join(secrets.choice(string.digits) for _ in range(3))
    return f"{category_code}-{name_code}-{random_part}"

def format_currency(amount: float, currency: str = "USD") -> str:
    """Format currency amount"""
    if currency == "USD":
        return f"${amount:.2f}"
    return f"{amount:.2f} {currency}"

def calculate_tax(subtotal: Decimal, tax_rate: float = 0.08) -> Decimal:
    """Calculate tax amount"""
    return Decimal(str(round(float(subtotal) * tax_rate, 2)))

def calculate_shipping_cost(subtotal: Decimal, shipping_address: Dict[str, Any]) -> Decimal:
    """Calculate shipping cost based on order value and address"""
    base_rate = Decimal('5.00')
    
    # Free shipping for orders over $100
    if subtotal >= Decimal('100.00'):
        return Decimal('0.00')
    
    # Different rates based on location (simplified)
    country = shipping_address.get('country', '').lower()
    if country in ['us', 'usa', 'united states']:
        return base_rate
    elif country in ['ca', 'canada', 'mx', 'mexico']:
        return base_rate * Decimal('1.5')
    else:  # International
        return base_rate * Decimal('2.5')

def calculate_shipping(weight: float, distance: str = "local") -> float:
    """Calculate shipping cost based on weight and distance (legacy function)"""
    base_rate = 5.00
    weight_rate = 2.00  # per kg
    
    if distance == "local":
        multiplier = 1.0
    elif distance == "national":
        multiplier = 1.5
    else:  # international
        multiplier = 3.0
    
    return round((base_rate + (weight * weight_rate)) * multiplier, 2)

class PaginationParams:
    """Pagination parameters helper"""
    def __init__(self, page: int = 1, limit: int = 10, max_limit: int = 100):
        self.page = max(1, page)
        self.limit = min(max_limit, max(1, limit))
        self.offset = (self.page - 1) * self.limit
    
    def get_offset(self) -> int:
        return self.offset
    
    def get_limit(self) -> int:
        return self.limit
    
    def get_page(self) -> int:
        return self.page