ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS subdomain TEXT,
  ADD COLUMN IF NOT EXISTS primary_hostname TEXT,
  ADD COLUMN IF NOT EXISTS booking_site_enabled BOOLEAN DEFAULT true,
  ADD COLUMN IF NOT EXISTS domain_status TEXT DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS domain_verified_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS domain_last_checked_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS domain_last_error TEXT,
  ADD COLUMN IF NOT EXISTS booking_theme JSONB DEFAULT '{}'::jsonb;

UPDATE tenants
SET subdomain = slug
WHERE subdomain IS NULL;

UPDATE tenants
SET booking_site_enabled = true
WHERE booking_site_enabled IS NULL;

UPDATE tenants
SET booking_theme = '{}'::jsonb
WHERE booking_theme IS NULL;

UPDATE tenants
SET domain_status = CASE
  WHEN domain IS NOT NULL AND btrim(domain) <> '' THEN 'pending'
  ELSE 'none'
END
WHERE domain_status IS NULL OR btrim(domain_status) = '';

UPDATE tenants
SET primary_hostname = CASE
  WHEN lower(COALESCE(domain_status, 'none')) = 'verified' AND domain IS NOT NULL AND btrim(domain) <> '' THEN lower(btrim(domain))
  ELSE subdomain
END
WHERE primary_hostname IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_subdomain_lower
  ON tenants(lower(subdomain))
  WHERE subdomain IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_domain_lower
  ON tenants(lower(domain))
  WHERE domain IS NOT NULL;
