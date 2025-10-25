import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from shared.db import db_manager
from .models import (
    UserCreateRequest, UserUpdateRequest, AdminUserResponse,
    AdminOrderResponse
)

logger = logging.getLogger(__name__)

class AdminManager:
    """Admin business logic manager"""
    
    async def get_users(
        self,
        page: int = 1,
        limit: int = 20,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        email_verified: Optional[bool] = None,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Get paginated list of users with filtering"""
        
        # Build base query
        where_conditions = []
        params = []
        param_count = 0
        
        # Apply filters
        if role:
            param_count += 1
            where_conditions.append(f"u.role = ${param_count}")
            params.append(role)
        
        if is_active is not None:
            param_count += 1
            where_conditions.append(f"u.is_active = ${param_count}")
            params.append(is_active)
        
        if email_verified is not None:
            param_count += 1
            where_conditions.append(f"u.email_verified = ${param_count}")
            params.append(email_verified)
        
        if search:
            param_count += 1
            search_param = param_count
            param_count += 1
            where_conditions.append(f"(u.name ILIKE ${search_param} OR u.email ILIKE ${param_count})")
            params.append(f"%{search}%")
            params.append(f"%{search}%")
        
        if date_from:
            try:
                date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                param_count += 1
                where_conditions.append(f"u.created_at >= ${param_count}")
                params.append(date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                param_count += 1
                where_conditions.append(f"u.created_at <= ${param_count}")
                params.append(date_to_obj)
            except ValueError:
                pass
        
        # Build WHERE clause
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # Build ORDER BY clause
        valid_sort_columns = ["id", "name", "email", "role", "created_at", "updated_at"]
        if sort_by not in valid_sort_columns:
            sort_by = "created_at"
        
        order_direction = "DESC" if sort_order.lower() == "desc" else "ASC"
        order_clause = f"ORDER BY u.{sort_by} {order_direction}"
        
        # Get total count for pagination
        count_query = f"SELECT COUNT(*) FROM users u LEFT JOIN addresses a ON u.id = a.user_id AND a.is_default = true {where_clause}"
        total = await db_manager.fetch_val(count_query, *params)
        
        # Apply pagination
        offset = (page - 1) * limit
        
        # Build main query with phone number from addresses
        query = f"""
            SELECT u.id, u.email, u.name, u.role, u.email_verified, u.is_active, 
                   u.created_at, u.updated_at, a.phone
            FROM users u
            LEFT JOIN addresses a ON u.id = a.user_id AND a.is_default = true
            {where_clause}
            {order_clause}
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """
        
        # Execute query
        users_data = await db_manager.fetch_all(query, *params, limit, offset)
        
        # Convert datetime objects to ISO strings
        for user in users_data:
            if user.get('created_at'):
                user['created_at'] = user['created_at'].isoformat()
            if user.get('updated_at'):
                user['updated_at'] = user['updated_at'].isoformat()
        
        return {
            "users": users_data,
            "total": total
        }

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get specific user by ID with additional stats"""
        # Get user basic info
        user_query = """
            SELECT id, email, name, role, email_verified, is_active, 
                   created_at, updated_at
            FROM users 
            WHERE id = $1
        """
        
        user = await db_manager.fetch_one(user_query, user_id)
        
        if not user:
            return None
        
        # Get user address info (using default address for profile data)
        profile_query = """
            SELECT phone, address1 as address, city, state, country, zip_code as postal_code
            FROM addresses 
            WHERE user_id = $1 AND is_default = true
            LIMIT 1
        """
        
        profile = await db_manager.fetch_one(profile_query, user_id)
        
        # Get user order statistics (focus on completed orders)
        stats_query = """
            SELECT 
                COUNT(*) as order_count,
                COALESCE(SUM(total), 0) as total_spent,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_orders,
                COALESCE(SUM(CASE WHEN status = 'completed' THEN total ELSE 0 END), 0) as completed_spent
            FROM orders 
            WHERE user_id = $1 AND status != 'cancelled'
        """
        
        stats = await db_manager.fetch_one(stats_query, user_id)
        
        # Convert to proper format
        result = dict(user)
        
        # Convert datetime objects to ISO strings
        if result.get('created_at'):
            result['created_at'] = result['created_at'].isoformat()
        if result.get('updated_at'):
            result['updated_at'] = result['updated_at'].isoformat()
        
        # Add profile info
        if profile:
            result['profile'] = dict(profile)
        else:
            result['profile'] = None
        
        # Add statistics with completed orders focus
        if stats:
            result['order_count'] = stats['order_count']
            result['total_spent'] = float(stats['total_spent']) if stats['total_spent'] else 0.0
            result['completed_orders'] = stats['completed_orders']
            result['completed_spent'] = float(stats['completed_spent']) if stats['completed_spent'] else 0.0
        else:
            result['order_count'] = 0
            result['total_spent'] = 0.0
            result['completed_orders'] = 0
            result['completed_spent'] = 0.0
        
        return result

    async def create_user(self, user_data: UserCreateRequest) -> Dict[str, Any]:
        """Create a new user"""
        from shared.utils import get_password_hash
        import uuid
        
        # Hash the password
        hashed_password = get_password_hash(user_data.password)
        
        # Generate user ID
        user_id = str(uuid.uuid4())
        
        # Insert user
        insert_query = """
            INSERT INTO users (id, email, name, password_hash, role, is_active, email_verified, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id, email, name, role, email_verified, is_active, created_at, updated_at
        """
        
        now = datetime.utcnow()
        
        user = await db_manager.fetch_one(
            insert_query,
            user_id,
            user_data.email,
            user_data.name,
            hashed_password,
            user_data.role,
            user_data.is_active,
            False,  # email_verified starts as False
            now,
            now
        )
        
        # Create user address if phone is provided
        if user_data.phone:
            address_query = """
                INSERT INTO addresses (user_id, first_name, last_name, address1, city, state, zip_code, country, phone, is_default, address_type, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """
            # Use name parts for first/last name, with defaults for required fields
            name_parts = user_data.name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            await db_manager.execute_query(
                address_query, 
                user_id, 
                first_name, 
                last_name, 
                'Address not provided',  # address1
                'City not provided',     # city
                'State not provided',    # state
                '00000',                 # zip_code
                'Country not provided',  # country
                user_data.phone, 
                True,                    # is_default
                'both',                  # address_type
                now, 
                now
            )
        
        # Convert to proper format
        result = dict(user)
        
        # Convert datetime objects to ISO strings
        if result.get('created_at'):
            result['created_at'] = result['created_at'].isoformat()
        if result.get('updated_at'):
            result['updated_at'] = result['updated_at'].isoformat()
        
        return result

    async def update_user(self, user_id: str, user_data: UserUpdateRequest) -> Optional[Dict[str, Any]]:
        """Update user information"""
        # Build dynamic update query
        update_fields = []
        params = []
        param_count = 0
        
        if user_data.name is not None:
            param_count += 1
            update_fields.append(f"name = ${param_count}")
            params.append(user_data.name)
        
        if user_data.email is not None:
            param_count += 1
            update_fields.append(f"email = ${param_count}")
            params.append(user_data.email)
        
        if user_data.role is not None:
            param_count += 1
            update_fields.append(f"role = ${param_count}")
            params.append(user_data.role)
        
        if user_data.is_active is not None:
            param_count += 1
            update_fields.append(f"is_active = ${param_count}")
            params.append(user_data.is_active)
        
        if not update_fields:
            # No fields to update, return current user
            return await self.get_user_by_id(user_id)
        
        # Add updated_at
        param_count += 1
        update_fields.append(f"updated_at = ${param_count}")
        params.append(datetime.utcnow())
        
        # Add user_id for WHERE clause
        param_count += 1
        params.append(user_id)
        
        # Build and execute update query
        update_query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}
            WHERE id = ${param_count}
            RETURNING id, email, name, role, email_verified, is_active, 
                      created_at, updated_at
        """
        
        user = await db_manager.fetch_one(update_query, *params)
        
        if not user:
            return None
        
        # Update address if phone is provided
        if user_data.phone is not None:
            # Check if user has a default address
            check_address_query = """
                SELECT id FROM addresses WHERE user_id = $1 AND is_default = true LIMIT 1
            """
            existing_address = await db_manager.fetch_one(check_address_query, user_id)
            
            if existing_address:
                # Update existing default address
                address_update_query = """
                    UPDATE addresses 
                    SET phone = $1, updated_at = $2 
                    WHERE user_id = $3 AND is_default = true
                """
                await db_manager.execute_query(
                    address_update_query, 
                    user_data.phone, 
                    datetime.utcnow(), 
                    user_id
                )
            else:
                # Create new default address with phone
                name_parts = user.get('name', '').split(' ', 1)
                first_name = name_parts[0] if name_parts else 'User'
                last_name = name_parts[1] if len(name_parts) > 1 else ''
                
                address_insert_query = """
                    INSERT INTO addresses (user_id, first_name, last_name, address1, city, state, zip_code, country, phone, is_default, address_type, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """
                await db_manager.execute_query(
                    address_insert_query,
                    user_id,
                    first_name,
                    last_name,
                    'Address not provided',
                    'City not provided',
                    'State not provided',
                    '00000',
                    'Country not provided',
                    user_data.phone,
                    True,
                    'both',
                    datetime.utcnow(),
                    datetime.utcnow()
                )
        
        # Convert to proper format
        result = dict(user)
        
        # Convert datetime objects to ISO strings
        if result.get('created_at'):
            result['created_at'] = result['created_at'].isoformat()
        if result.get('updated_at'):
            result['updated_at'] = result['updated_at'].isoformat()
        
        return result

    async def delete_user(self, user_id: str) -> bool:
        """Soft delete a user by deactivating them"""
        update_query = """
            UPDATE users 
            SET is_active = false, updated_at = $1 
            WHERE id = $2
        """
        
        result = await db_manager.execute_query(update_query, datetime.utcnow(), user_id)
        return result is not None

    async def update_user_role(self, user_id: str, new_role: str) -> Optional[Dict[str, Any]]:
        """Update user role"""
        if new_role not in ['customer', 'designer', 'admin']:
            raise ValueError("Invalid role")
        
        # Update the user role
        update_query = """
            UPDATE users 
            SET role = $1, updated_at = $2 
            WHERE id = $3
            RETURNING id, email, name, role, email_verified, is_active, 
                      created_at, updated_at
        """
        
        updated_user = await db_manager.fetch_one(
            update_query, 
            new_role, 
            datetime.utcnow(), 
            user_id
        )
        
        if not updated_user:
            return None
        
        # Convert to proper format
        result = dict(updated_user)
        
        # Convert datetime objects to ISO strings
        if result.get('created_at'):
            result['created_at'] = result['created_at'].isoformat()
        if result.get('updated_at'):
            result['updated_at'] = result['updated_at'].isoformat()
        
        return result

    async def update_user_status(self, user_id: str, is_active: bool) -> Optional[Dict[str, Any]]:
        """Update user active status"""
        # Update the user status
        update_query = """
            UPDATE users 
            SET is_active = $1, updated_at = $2 
            WHERE id = $3
            RETURNING id, email, name, role, email_verified, is_active, 
                      created_at, updated_at
        """
        
        updated_user = await db_manager.fetch_one(
            update_query, 
            is_active, 
            datetime.utcnow(), 
            user_id
        )
        
        if not updated_user:
            return None
        
        # Convert to proper format
        result = dict(updated_user)
        
        # Convert datetime objects to ISO strings
        if result.get('created_at'):
            result['created_at'] = result['created_at'].isoformat()
        if result.get('updated_at'):
            result['updated_at'] = result['updated_at'].isoformat()
        
        return result

    async def get_user_statistics(self) -> Dict[str, Any]:
        """Get user statistics for admin dashboard"""
        stats_query = """
            SELECT 
                COUNT(*) as total_users,
                COUNT(*) FILTER (WHERE is_active = true) as active_users,
                COUNT(*) FILTER (WHERE role = 'customer') as customers,
                COUNT(*) FILTER (WHERE role = 'designer') as designers,
                COUNT(*) FILTER (WHERE role = 'admin') as admins,
                COUNT(*) FILTER (WHERE email_verified = true) as verified_users
            FROM users
        """
        
        stats = await db_manager.fetch_one(stats_query)
        
        if not stats:
            return {
                "total_users": 0,
                "active_users": 0,
                "customers": 0,
                "designers": 0,
                "admins": 0,
                "verified_users": 0
            }
        
        return dict(stats)

# Create global instance
admin_manager = AdminManager()
