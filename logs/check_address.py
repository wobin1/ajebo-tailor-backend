import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv('/Applications/wobin/ajebo-tailor/backend-api/src/.env')

async def check_address():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Check the address
    address = await conn.fetchrow(
        "SELECT * FROM addresses WHERE id = $1",
        'b6a8ff6b-f088-44ad-b851-579bc1dcb67d'
    )
    print("Address:", dict(address) if address else "Not found")
    
    # Check the user who made the order request
    user = await conn.fetchrow(
        "SELECT id, email, first_name, last_name FROM users WHERE email = $1",
        'nathanielmusa3@gmail.com'
    )
    print("\nUser:", dict(user) if user else "Not found")
    
    # Check all addresses for this user
    user_addresses = await conn.fetch(
        "SELECT id, street_address, city FROM addresses WHERE user_id = $1",
        user['id'] if user else None
    )
    print(f"\nUser's addresses ({len(user_addresses)}):")
    for addr in user_addresses:
        print(f"  - {addr['id']}: {addr['street_address']}, {addr['city']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_address())
