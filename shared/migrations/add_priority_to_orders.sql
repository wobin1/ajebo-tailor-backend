-- Migration: Add priority field to orders table
-- Date: 2025-01-13
-- Description: Add priority column to orders table with enum constraint

-- Add priority column to orders table
ALTER TABLE orders 
ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'medium' 
CHECK (priority IN ('low', 'medium', 'high', 'urgent'));

-- Create index for priority filtering
CREATE INDEX IF NOT EXISTS idx_orders_priority ON orders(priority);

-- Update existing orders to have medium priority (default)
UPDATE orders SET priority = 'medium' WHERE priority IS NULL;

-- Add priority to the status check constraint (update existing constraint)
ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_status_check;
ALTER TABLE orders ADD CONSTRAINT orders_status_check 
CHECK (status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded'));

-- Comment on the new column
COMMENT ON COLUMN orders.priority IS 'Order priority level: low, medium, high, urgent';
