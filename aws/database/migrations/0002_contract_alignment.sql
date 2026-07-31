-- Reconcile installations created from historical AIR BEE schema files.

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS subdomain TEXT,
  ADD COLUMN IF NOT EXISTS domain TEXT,
  ADD COLUMN IF NOT EXISTS primary_hostname TEXT,
  ADD COLUMN IF NOT EXISTS booking_site_enabled BOOLEAN DEFAULT true,
  ADD COLUMN IF NOT EXISTS domain_status TEXT DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS domain_verified_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS domain_last_checked_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS domain_last_error TEXT,
  ADD COLUMN IF NOT EXISTS domain_config JSONB DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS booking_theme JSONB DEFAULT '{}'::jsonb;

UPDATE tenants
SET
  subdomain = COALESCE(NULLIF(subdomain, ''), slug),
  primary_hostname = COALESCE(NULLIF(primary_hostname, ''), NULLIF(subdomain, ''), slug),
  booking_site_enabled = COALESCE(booking_site_enabled, true),
  domain_status = COALESCE(NULLIF(domain_status, ''), 'none'),
  domain_config = COALESCE(domain_config, '{}'::jsonb),
  settings = COALESCE(settings, '{}'::jsonb),
  booking_theme = COALESCE(booking_theme, '{}'::jsonb);

ALTER TABLE rooms
  ADD COLUMN IF NOT EXISTS minimum_stay INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS base_occupancy INTEGER DEFAULT 2,
  ADD COLUMN IF NOT EXISTS extra_guest_fee NUMERIC(10,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS check_in_time TEXT DEFAULT '14:00',
  ADD COLUMN IF NOT EXISTS check_out_time TEXT DEFAULT '11:00',
  ADD COLUMN IF NOT EXISTS cancellation_policy TEXT,
  ADD COLUMN IF NOT EXISTS ical_feed_token UUID DEFAULT gen_random_uuid();

UPDATE rooms
SET
  minimum_stay = COALESCE(minimum_stay, 1),
  base_occupancy = COALESCE(base_occupancy, 2),
  extra_guest_fee = COALESCE(extra_guest_fee, 0),
  check_in_time = COALESCE(check_in_time, '14:00'),
  check_out_time = COALESCE(check_out_time, '11:00'),
  ical_feed_token = COALESCE(ical_feed_token, gen_random_uuid());

ALTER TABLE rooms ALTER COLUMN ical_feed_token SET DEFAULT gen_random_uuid();
ALTER TABLE rooms ALTER COLUMN ical_feed_token SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_rooms_ical_feed_token ON rooms (ical_feed_token);

ALTER TABLE bookings
  ADD COLUMN IF NOT EXISTS booking_source TEXT DEFAULT 'direct',
  ADD COLUMN IF NOT EXISTS source_channel TEXT DEFAULT 'direct',
  ADD COLUMN IF NOT EXISTS external_uid TEXT;

UPDATE bookings
SET
  booking_source = COALESCE(NULLIF(booking_source, ''), 'direct'),
  source_channel = COALESCE(NULLIF(source_channel, ''), 'direct');

ALTER TABLE room_pricing_rules
  ADD COLUMN IF NOT EXISTS adjustment_type TEXT DEFAULT 'percentage',
  ADD COLUMN IF NOT EXISTS adjustment_value NUMERIC(10,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS min_nights INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

ALTER TABLE campaigns
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'room_pricing_rules'
      AND column_name = 'modifier_type'
  ) THEN
    EXECUTE 'UPDATE room_pricing_rules
             SET adjustment_type = COALESCE(NULLIF(adjustment_type, ''''), modifier_type, ''percentage'')';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'room_pricing_rules'
      AND column_name = 'price_modifier'
  ) THEN
    EXECUTE 'UPDATE room_pricing_rules
             SET adjustment_value = COALESCE(adjustment_value, price_modifier, 0)';
  END IF;
END
$$;

UPDATE room_pricing_rules
SET
  adjustment_type = COALESCE(NULLIF(adjustment_type, ''), 'percentage'),
  adjustment_value = COALESCE(adjustment_value, 0),
  min_nights = COALESCE(min_nights, 1),
  priority = COALESCE(priority, 1),
  updated_at = COALESCE(updated_at, created_at, now());

ALTER TABLE booking_payments
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS payment_date DATE DEFAULT CURRENT_DATE,
  ADD COLUMN IF NOT EXISTS received_at TIMESTAMPTZ DEFAULT now(),
  ADD COLUMN IF NOT EXISTS received_by VARCHAR(255),
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();

UPDATE booking_payments bp
SET tenant_id = b.tenant_id
FROM bookings b
WHERE bp.booking_id = b.id AND bp.tenant_id IS NULL;

UPDATE booking_payments
SET
  payment_date = COALESCE(payment_date, received_at::date, created_at::date, CURRENT_DATE),
  received_at = COALESCE(received_at, created_at, now()),
  created_at = COALESCE(created_at, received_at, now());

ALTER TABLE booking_payments ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE booking_payments ALTER COLUMN payment_date SET NOT NULL;
ALTER TABLE booking_payments ALTER COLUMN received_at SET NOT NULL;

ALTER TABLE invoices
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS tax_amount NUMERIC(10,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_amount NUMERIC(10,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS issued_at TIMESTAMPTZ DEFAULT now(),
  ADD COLUMN IF NOT EXISTS due_date DATE,
  ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS notes TEXT,
  ADD COLUMN IF NOT EXISTS pdf_url TEXT,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

UPDATE invoices i
SET tenant_id = b.tenant_id
FROM bookings b
WHERE i.booking_id = b.id AND i.tenant_id IS NULL;

UPDATE invoices
SET
  tax_amount = COALESCE(tax_amount, 0),
  total_amount = CASE WHEN COALESCE(total_amount, 0) = 0 THEN COALESCE(amount, 0) ELSE total_amount END,
  status = COALESCE(NULLIF(status, ''), 'draft'),
  issued_at = COALESCE(issued_at, created_at, now()),
  created_at = COALESCE(created_at, issued_at, now()),
  updated_at = COALESCE(updated_at, created_at, now());

ALTER TABLE invoices ALTER COLUMN tenant_id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_tenant_number
  ON invoices (tenant_id, invoice_number);

ALTER TABLE message_templates
  ADD COLUMN IF NOT EXISTS name TEXT DEFAULT 'Untitled Template',
  ADD COLUMN IF NOT EXISTS channel TEXT DEFAULT 'email',
  ADD COLUMN IF NOT EXISTS subject TEXT,
  ADD COLUMN IF NOT EXISTS content TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS variables JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'message_templates' AND column_name = 'template_name'
  ) THEN
    EXECUTE 'UPDATE message_templates
             SET name = COALESCE(NULLIF(name, ''''), NULLIF(template_name, ''''), ''Untitled Template''),
                 template_name = COALESCE(NULLIF(template_name, ''''), NULLIF(name, ''''), ''Untitled Template'')';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'message_templates' AND column_name = 'body'
  ) THEN
    EXECUTE 'UPDATE message_templates
             SET content = COALESCE(content, body, ''''),
                 body = COALESCE(body, content, '''')';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'message_templates' AND column_name = 'status'
  ) THEN
    EXECUTE 'UPDATE message_templates
             SET is_active = COALESCE(is_active, status = ''active''),
                 status = COALESCE(NULLIF(status, ''''), CASE WHEN COALESCE(is_active, true) THEN ''active'' ELSE ''inactive'' END)';
  END IF;
END
$$;

UPDATE message_templates
SET
  name = COALESCE(NULLIF(name, ''), 'Untitled Template'),
  channel = COALESCE(NULLIF(channel, ''), 'email'),
  content = COALESCE(content, ''),
  variables = COALESCE(variables, '[]'::jsonb),
  is_active = COALESCE(is_active, true),
  created_at = COALESCE(created_at, now()),
  updated_at = COALESCE(updated_at, created_at, now());

ALTER TABLE message_logs
  ADD COLUMN IF NOT EXISTS campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS template_id UUID REFERENCES message_templates(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS channel TEXT DEFAULT 'email',
  ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'messaging',
  ADD COLUMN IF NOT EXISTS recipient_name TEXT,
  ADD COLUMN IF NOT EXISTS recipient_email TEXT,
  ADD COLUMN IF NOT EXISTS recipient_phone TEXT,
  ADD COLUMN IF NOT EXISTS subject TEXT,
  ADD COLUMN IF NOT EXISTS content TEXT,
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'logged',
  ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();

DO $$
DECLARE
  constraint_name TEXT;
BEGIN
  FOR constraint_name IN
    SELECT con.conname
    FROM pg_constraint con
    JOIN pg_class source_table ON source_table.oid = con.conrelid
    JOIN pg_class target_table ON target_table.oid = con.confrelid
    WHERE con.contype = 'f'
      AND source_table.relname = 'message_logs'
      AND target_table.relname = 'message_campaigns'
  LOOP
    EXECUTE format('ALTER TABLE message_logs DROP CONSTRAINT %I', constraint_name);
  END LOOP;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint con
    JOIN pg_class source_table ON source_table.oid = con.conrelid
    JOIN pg_class target_table ON target_table.oid = con.confrelid
    WHERE con.contype = 'f'
      AND source_table.relname = 'message_logs'
      AND target_table.relname = 'campaigns'
  ) THEN
    ALTER TABLE message_logs
      ADD CONSTRAINT message_logs_campaign_id_fkey
      FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL;
  END IF;
END
$$;

UPDATE message_logs
SET
  channel = COALESCE(NULLIF(channel, ''), 'email'),
  source = COALESCE(NULLIF(source, ''), 'messaging'),
  status = COALESCE(NULLIF(status, ''), 'logged'),
  metadata = COALESCE(metadata, '{}'::jsonb),
  created_at = COALESCE(created_at, now());

CREATE TABLE IF NOT EXISTS marketing_segments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  rules JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, key)
);

CREATE TABLE IF NOT EXISTS maintenance_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  room_id UUID REFERENCES rooms(id) ON DELETE SET NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  priority VARCHAR(20) NOT NULL DEFAULT 'normal',
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  reported_by VARCHAR(255),
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS expenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  category VARCHAR(100) NOT NULL DEFAULT 'other',
  description TEXT NOT NULL,
  amount NUMERIC(12,2) NOT NULL DEFAULT 0,
  expense_date DATE NOT NULL DEFAULT CURRENT_DATE,
  payment_method VARCHAR(50) NOT NULL DEFAULT 'cash',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staff_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255),
  phone VARCHAR(50),
  role VARCHAR(50) NOT NULL DEFAULT 'staff',
  department VARCHAR(100),
  is_active BOOLEAN NOT NULL DEFAULT true,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  type VARCHAR(50) NOT NULL,
  title VARCHAR(255) NOT NULL,
  message TEXT,
  is_read BOOLEAN NOT NULL DEFAULT false,
  related_id UUID,
  related_type VARCHAR(50),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id VARCHAR(255),
  action VARCHAR(100) NOT NULL,
  entity_type VARCHAR(100) NOT NULL,
  entity_id UUID,
  old_value JSONB,
  new_value JSONB,
  ip_address VARCHAR(50),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS waitlist (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  room_id UUID REFERENCES rooms(id) ON DELETE CASCADE,
  guest_name VARCHAR(255) NOT NULL,
  guest_email VARCHAR(255) NOT NULL,
  guest_phone VARCHAR(50),
  check_in DATE NOT NULL,
  check_out DATE NOT NULL,
  guests INTEGER NOT NULL DEFAULT 1,
  status VARCHAR(20) NOT NULL DEFAULT 'waiting',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS channels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  platform TEXT NOT NULL DEFAULT 'other',
  room_id UUID REFERENCES rooms(id) ON DELETE CASCADE,
  ical_url TEXT,
  last_synced_at TIMESTAMPTZ,
  sync_status TEXT NOT NULL DEFAULT 'pending',
  sync_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE audit_logs
  ALTER COLUMN user_id TYPE VARCHAR(255) USING user_id::text;

CREATE INDEX IF NOT EXISTS idx_booking_payments_tenant_received
  ON booking_payments (tenant_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_pricing_rules_tenant_active
  ON room_pricing_rules (tenant_id, is_active, priority);
CREATE INDEX IF NOT EXISTS idx_invoices_tenant_issued
  ON invoices (tenant_id, issued_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_tenant_unread
  ON notifications (tenant_id, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_created
  ON audit_logs (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_channels_tenant ON channels (tenant_id);
CREATE INDEX IF NOT EXISTS idx_channels_room ON channels (room_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_external_uid
  ON bookings (tenant_id, room_id, external_uid) WHERE external_uid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_room_categories_tenant_name
  ON room_categories (tenant_id, lower(name));

DROP TRIGGER IF EXISTS update_campaigns_updated_at ON campaigns;
CREATE TRIGGER update_campaigns_updated_at
  BEFORE UPDATE ON campaigns FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
