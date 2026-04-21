ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS domain_config JSONB DEFAULT '{}'::jsonb;

UPDATE tenants
SET domain_config = '{}'::jsonb
WHERE domain_config IS NULL;
