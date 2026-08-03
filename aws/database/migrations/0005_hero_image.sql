-- Dedicated hero image for the public booking page, distinct from room photos.
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS hero_image_url TEXT;
