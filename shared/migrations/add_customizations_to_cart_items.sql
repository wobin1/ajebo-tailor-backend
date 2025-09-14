-- Migration: Add customizations column to cart_items table
-- Date: 2025-09-05

-- Add customizations column to cart_items table
ALTER TABLE cart_items 
ADD COLUMN IF NOT EXISTS customizations JSONB;
