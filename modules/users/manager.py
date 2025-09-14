import logging
from typing import Optional, List
from shared.db import db_manager
from shared.response import NotFoundException, ValidationException
from modules.auth.models import UserResponse
from .models import UserUpdate, AddressCreate, AddressUpdate, AddressResponse

logger = logging.getLogger(__name__)

class UserManager:
    """User management business logic"""
    
    async def update_user(self, user_id: str, user_data: UserUpdate) -> UserResponse:
        """Update user profile"""
        try:
            # Check if user exists
            existing_user = await db_manager.fetch_one(
                "SELECT id FROM users WHERE id = $1 AND is_active = true",
                user_id
            )
            
            if not existing_user:
                raise NotFoundException("User")
            
            # Build update query dynamically
            update_fields = []
            values = []
            param_count = 1
            
            if user_data.name is not None:
                update_fields.append(f"name = ${param_count}")
                values.append(user_data.name)
                param_count += 1
            
            if user_data.avatar is not None:
                update_fields.append(f"avatar = ${param_count}")
                values.append(user_data.avatar)
                param_count += 1
            
            if not update_fields:
                # No fields to update, return current user
                return await self.get_user_by_id(user_id)
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(user_id)
            
            query = f"""
                UPDATE users 
                SET {', '.join(update_fields)}
                WHERE id = ${param_count}
            """
            
            await db_manager.execute_query(query, *values)
            
            # Return updated user
            updated_user = await self.get_user_by_id(user_id)
            logger.info(f"User updated successfully: {user_id}")
            
            return updated_user
            
        except Exception as e:
            logger.error(f"Failed to update user: {e}")
            raise
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """Get user by ID"""
        try:
            user_data = await db_manager.fetch_one(
                """
                SELECT id, email, name, avatar, role, is_active, 
                       email_verified, created_at, updated_at
                FROM users 
                WHERE id = $1 AND is_active = true
                """,
                user_id
            )
            
            if not user_data:
                return None
            
            return UserResponse(
                id=str(user_data["id"]),
                email=user_data["email"],
                name=user_data["name"],
                avatar=user_data["avatar"],
                role=user_data["role"],
                is_active=user_data["is_active"],
                email_verified=user_data["email_verified"],
                created_at=user_data["created_at"],
                updated_at=user_data["updated_at"]
            )
            
        except Exception as e:
            logger.error(f"Failed to get user by ID: {e}")
            return None
    
    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user account"""
        try:
            result = await db_manager.execute_query(
                "UPDATE users SET is_active = false, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                user_id
            )
            
            logger.info(f"User deactivated: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to deactivate user: {e}")
            return False
    
    # Address management
    async def create_address(self, user_id: str, address_data: AddressCreate) -> AddressResponse:
        """Create new address for user"""
        try:
            # If this is set as default, unset other default addresses
            if address_data.is_default:
                await db_manager.execute_query(
                    "UPDATE addresses SET is_default = false WHERE user_id = $1",
                    user_id
                )
            
            # Create address
            address_id = await db_manager.fetch_val(
                """
                INSERT INTO addresses (
                    user_id, first_name, last_name, company, address1, address2,
                    city, state, zip_code, country, phone, is_default, address_type
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING id
                """,
                user_id, address_data.first_name, address_data.last_name,
                address_data.company, address_data.address1, address_data.address2,
                address_data.city, address_data.state, address_data.zip_code,
                address_data.country, address_data.phone, address_data.is_default,
                address_data.address_type
            )
            
            # Return created address
            address = await self.get_address_by_id(str(address_id))
            logger.info(f"Address created for user {user_id}: {address_id}")
            
            return address
            
        except Exception as e:
            logger.error(f"Failed to create address: {e}")
            raise
    
    async def get_user_addresses(self, user_id: str) -> List[AddressResponse]:
        """Get all addresses for a user"""
        try:
            addresses_data = await db_manager.fetch_all(
                """
                SELECT id, user_id, first_name, last_name, company, address1, address2,
                       city, state, zip_code, country, phone, is_default, address_type,
                       created_at, updated_at
                FROM addresses 
                WHERE user_id = $1
                ORDER BY is_default DESC, created_at DESC
                """,
                user_id
            )
            
            return [
                AddressResponse(
                    id=str(addr["id"]),
                    user_id=str(addr["user_id"]),
                    first_name=addr["first_name"],
                    last_name=addr["last_name"],
                    company=addr["company"],
                    address1=addr["address1"],
                    address2=addr["address2"],
                    city=addr["city"],
                    state=addr["state"],
                    zip_code=addr["zip_code"],
                    country=addr["country"],
                    phone=addr["phone"],
                    is_default=addr["is_default"],
                    address_type=addr["address_type"],
                    created_at=addr["created_at"],
                    updated_at=addr["updated_at"]
                )
                for addr in addresses_data
            ]
            
        except Exception as e:
            logger.error(f"Failed to get user addresses: {e}")
            return []
    
    async def get_address_by_id(self, address_id: str) -> Optional[AddressResponse]:
        """Get address by ID"""
        try:
            addr_data = await db_manager.fetch_one(
                """
                SELECT id, user_id, first_name, last_name, company, address1, address2,
                       city, state, zip_code, country, phone, is_default, address_type,
                       created_at, updated_at
                FROM addresses 
                WHERE id = $1
                """,
                address_id
            )
            
            if not addr_data:
                return None
            
            return AddressResponse(
                id=str(addr_data["id"]),
                user_id=str(addr_data["user_id"]),
                first_name=addr_data["first_name"],
                last_name=addr_data["last_name"],
                company=addr_data["company"],
                address1=addr_data["address1"],
                address2=addr_data["address2"],
                city=addr_data["city"],
                state=addr_data["state"],
                zip_code=addr_data["zip_code"],
                country=addr_data["country"],
                phone=addr_data["phone"],
                is_default=addr_data["is_default"],
                address_type=addr_data["address_type"],
                created_at=addr_data["created_at"],
                updated_at=addr_data["updated_at"]
            )
            
        except Exception as e:
            logger.error(f"Failed to get address by ID: {e}")
            return None
    
    async def update_address(self, address_id: str, user_id: str, address_data: AddressUpdate) -> AddressResponse:
        """Update user address"""
        try:
            # Check if address exists and belongs to user
            existing_address = await db_manager.fetch_one(
                "SELECT id FROM addresses WHERE id = $1 AND user_id = $2",
                address_id, user_id
            )
            
            if not existing_address:
                raise NotFoundException("Address")
            
            # If setting as default, unset other defaults
            if address_data.is_default:
                await db_manager.execute_query(
                    "UPDATE addresses SET is_default = false WHERE user_id = $1",
                    user_id
                )
            
            # Build update query dynamically
            update_fields = []
            values = []
            param_count = 1
            
            for field, value in address_data.dict(exclude_unset=True).items():
                if value is not None:
                    update_fields.append(f"{field} = ${param_count}")
                    values.append(value)
                    param_count += 1
            
            if not update_fields:
                # No fields to update, return current address
                return await self.get_address_by_id(address_id)
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            values.extend([address_id, user_id])
            
            query = f"""
                UPDATE addresses 
                SET {', '.join(update_fields)}
                WHERE id = ${param_count} AND user_id = ${param_count + 1}
            """
            
            await db_manager.execute_query(query, *values)
            
            # Return updated address
            updated_address = await self.get_address_by_id(address_id)
            logger.info(f"Address updated: {address_id}")
            
            return updated_address
            
        except Exception as e:
            logger.error(f"Failed to update address: {e}")
            raise
    
    async def delete_address(self, address_id: str, user_id: str) -> bool:
        """Delete user address"""
        try:
            result = await db_manager.execute_query(
                "DELETE FROM addresses WHERE id = $1 AND user_id = $2",
                address_id, user_id
            )
            
            logger.info(f"Address deleted: {address_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete address: {e}")
            return False

# Global user manager instance
user_manager = UserManager()