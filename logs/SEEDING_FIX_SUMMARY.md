# Database Seeding Error Fix

## Problem
The application was crashing on startup with duplicate key constraint violations:
```
duplicate key value violates unique constraint "categories_slug_key"
DETAIL: Key (slug)=(mens-clothing) already exists.
```

## Root Cause
The `seed_initial_data()` function had insufficient checks:
1. Only checked if **users** existed before seeding
2. But categories, products, and admin user could already exist independently
3. No conflict handling in INSERT statements

## Solution Applied

### 1. Enhanced Data Check (Line 32-38)
**Before:**
```python
user_count = await db_manager.fetch_val("SELECT COUNT(*) FROM users")
if user_count > 0:
    logger.info("Database already has data, skipping seed")
    return
```

**After:**
```python
user_count = await db_manager.fetch_val("SELECT COUNT(*) FROM users")
category_count = await db_manager.fetch_val("SELECT COUNT(*) FROM categories")

if user_count > 0 or category_count > 0:
    logger.info("Database already has data, skipping seed")
    return
```

### 2. Added Conflict Handling for Categories (Line 52-60)
```python
INSERT INTO categories (name, slug, description, parent_id)
VALUES ($1, $2, $3, $4)
ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
RETURNING id
```

### 3. Added Conflict Handling for Admin User (Line 68-75)
```python
INSERT INTO users (email, name, password_hash, role, email_verified)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (email) DO NOTHING
```

### 4. Added Conflict Handling for Products (Line 125-138)
```python
INSERT INTO products (...)
VALUES (...)
ON CONFLICT (slug) DO NOTHING
```

## Benefits
✅ **Idempotent** - Can run multiple times safely  
✅ **No crashes** - Handles existing data gracefully  
✅ **Flexible** - Works even if database is partially seeded  
✅ **Production-safe** - Won't accidentally duplicate data  

## Testing
The app should now start successfully even if:
- Categories already exist
- Admin user already exists
- Products already exist
- Any combination of the above

## Files Modified
- `/Applications/wobin/ajebo-tailor/backend-api/src/shared/schema.py`
  - Updated `seed_initial_data()` function
  - Added comprehensive duplicate handling
