ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS domain_last_checked_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS domain_last_error TEXT;

UPDATE tenants
SET primary_hostname = CASE
  WHEN lower(COALESCE(domain_status, 'none')) = 'verified' AND domain IS NOT NULL AND btrim(domain) <> '' THEN lower(btrim(domain))
  ELSE COALESCE(NULLIF(subdomain, ''), slug)
END;
