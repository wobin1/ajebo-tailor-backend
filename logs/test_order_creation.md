# Order Creation Debugging Guide

## Issue Identified
The order creation is failing with a 422 error. Based on the logs, the issue is likely one of:
1. **Address doesn't belong to the user** - The address you're using was created by a different user
2. **Product not found or inactive** - The product ID might be invalid
3. **Insufficient stock** - The product might be out of stock

## Steps to Fix

### Step 1: Get Your User ID
First, login and check your user details:
```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nathanielmusa3@gmail.com","password":"YOUR_PASSWORD"}'

# Save the access_token from the response
```

### Step 2: Get Your Addresses
```bash
curl -X GET http://localhost:8000/api/v1/users/addresses \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Step 3: Create a New Address (if needed)
```bash
curl -X POST http://localhost:8000/api/v1/users/addresses \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "street_address": "123 Main St",
    "city": "Lagos",
    "state": "Lagos",
    "postal_code": "100001",
    "country": "Nigeria",
    "address_type": "both",
    "is_default": true
  }'
```

### Step 4: Get Available Products
```bash
curl -X GET "http://localhost:8000/api/v1/products?limit=10"
```

### Step 5: Create Order with Correct IDs
```bash
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
        {
            "product_id": "YOUR_PRODUCT_ID",
            "quantity": 1,
            "size": "M",
            "color": "Black",
            "customizations": {}
        }
    ],
    "shipping_address_id": "YOUR_ADDRESS_ID",
    "billing_address_id": "YOUR_ADDRESS_ID",
    "payment_method": "card"
  }'
```

## Current Error Analysis

From the terminal logs, I can see:
- User ID: `231eeb5a-d43e-4a90-bc15-af8771784405`
- Address created: `2daad726-d084-4c42-a4f2-976826a8cf00`
- The validation is running but failing

The next request should show detailed error messages in the terminal about what exactly is failing.
