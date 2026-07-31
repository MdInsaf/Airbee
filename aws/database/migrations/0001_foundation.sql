-- AIR BEE database foundation.
-- This migration is intentionally idempotent so an installation that predates
-- the migration ledger can adopt the authoritative sequence safely.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'app_role') THEN
    CREATE TYPE app_role AS ENUM ('owner', 'staff', 'guest');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'room_status') THEN
    CREATE TYPE room_status AS ENUM ('available', 'maintenance', 'unavailable');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'housekeeping_status') THEN
    CREATE TYPE housekeeping_status AS ENUM ('clean', 'dirty', 'in_progress', 'inspecting');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'booking_status') THEN
    CREATE TYPE booking_status AS ENUM ('pending', 'confirmed', 'cancelled', 'completed');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_status') THEN
    CREATE TYPE payment_status AS ENUM ('unpaid', 'partial', 'paid');
  END IF;
END
$$;

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  subdomain TEXT,
  domain TEXT,
  primary_hostname TEXT,
  booking_site_enabled BOOLEAN NOT NULL DEFAULT true,
  domain_status TEXT NOT NULL DEFAULT 'none',
  domain_verified_at TIMESTAMPTZ,
  domain_last_checked_at TIMESTAMPTZ,
  domain_last_error TEXT,
  domain_config JSONB NOT NULL DEFAULT '{}'::jsonb,
  settings JSONB NOT NULL DEFAULT '{}'::jsonb,
  booking_theme JSONB NOT NULL DEFAULT '{}'::jsonb,
  gst_enabled BOOLEAN NOT NULL DEFAULT false,
  gst_percentage NUMERIC(5,2) NOT NULL DEFAULT 0,
  gst_number TEXT,
  service_charge_enabled BOOLEAN NOT NULL DEFAULT false,
  service_charge_percentage NUMERIC(5,2) NOT NULL DEFAULT 0,
  email_settings JSONB NOT NULL DEFAULT '{}'::jsonb,
  contact_email TEXT,
  contact_phone TEXT,
  address TEXT,
  currency TEXT NOT NULL DEFAULT 'INR',
  timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
  logo_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS profiles (
  id VARCHAR(255) PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  full_name TEXT,
  phone TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(255) NOT NULL,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  role app_role NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, tenant_id, role)
);

CREATE TABLE IF NOT EXISTS room_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT '#3B82F6',
  display_order INTEGER NOT NULL DEFAULT 0,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS rooms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  category_id UUID REFERENCES room_categories(id) ON DELETE SET NULL,
  max_guests INTEGER NOT NULL DEFAULT 2 CHECK (max_guests > 0),
  base_price NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (base_price >= 0),
  status room_status NOT NULL DEFAULT 'available',
  amenities JSONB NOT NULL DEFAULT '[]'::jsonb,
  images JSONB NOT NULL DEFAULT '[]'::jsonb,
  housekeeping_status housekeeping_status NOT NULL DEFAULT 'clean',
  minimum_stay INTEGER NOT NULL DEFAULT 1 CHECK (minimum_stay > 0),
  base_occupancy INTEGER NOT NULL DEFAULT 2 CHECK (base_occupancy > 0),
  extra_guest_fee NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (extra_guest_fee >= 0),
  check_in_time TEXT NOT NULL DEFAULT '14:00',
  check_out_time TEXT NOT NULL DEFAULT '11:00',
  cancellation_policy TEXT,
  ical_feed_token UUID NOT NULL DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (ical_feed_token)
);

CREATE TABLE IF NOT EXISTS room_pricing_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  room_id UUID REFERENCES rooms(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  rule_type TEXT NOT NULL DEFAULT 'seasonal',
  adjustment_type TEXT NOT NULL DEFAULT 'percentage'
    CHECK (adjustment_type IN ('percentage', 'fixed')),
  adjustment_value NUMERIC(10,2) NOT NULL DEFAULT 0,
  start_date DATE,
  end_date DATE,
  days_of_week INTEGER[],
  min_nights INTEGER NOT NULL DEFAULT 1 CHECK (min_nights > 0),
  priority INTEGER NOT NULL DEFAULT 1,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS guest_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  email TEXT,
  name TEXT NOT NULL,
  phone TEXT,
  tags TEXT[] NOT NULL DEFAULT '{}'::text[],
  is_vip BOOLEAN NOT NULL DEFAULT false,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bookings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  room_id UUID NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  guest_id UUID REFERENCES guest_profiles(id) ON DELETE SET NULL,
  guest_name TEXT NOT NULL,
  guest_email TEXT,
  guest_phone TEXT,
  check_in DATE NOT NULL,
  check_out DATE NOT NULL,
  guests INTEGER NOT NULL DEFAULT 1 CHECK (guests > 0),
  total_amount NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
  base_amount NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (base_amount >= 0),
  tax_amount NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
  service_charge NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (service_charge >= 0),
  status booking_status NOT NULL DEFAULT 'pending',
  payment_status payment_status NOT NULL DEFAULT 'unpaid',
  payment_method TEXT,
  amount_paid NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (amount_paid >= 0),
  notes TEXT,
  booking_source TEXT NOT NULL DEFAULT 'direct',
  source_channel TEXT NOT NULL DEFAULT 'direct',
  external_uid TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (check_out > check_in)
);

CREATE TABLE IF NOT EXISTS booking_payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  amount NUMERIC(10,2) NOT NULL CHECK (amount > 0),
  payment_method TEXT NOT NULL DEFAULT 'cash',
  payment_date DATE NOT NULL DEFAULT CURRENT_DATE,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  received_by VARCHAR(255),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  invoice_number TEXT NOT NULL,
  amount NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
  tax_amount NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
  total_amount NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'issued', 'paid', 'void')),
  issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  due_date DATE,
  paid_at TIMESTAMPTZ,
  notes TEXT,
  pdf_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, invoice_number)
);

CREATE TABLE IF NOT EXISTS email_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  booking_id UUID REFERENCES bookings(id) ON DELETE SET NULL,
  email_type TEXT NOT NULL,
  recipient TEXT NOT NULL,
  subject TEXT,
  status TEXT NOT NULL DEFAULT 'sent',
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  title TEXT NOT NULL,
  content_blocks JSONB NOT NULL DEFAULT '[]'::jsonb,
  is_published BOOLEAN NOT NULL DEFAULT false,
  meta_title TEXT,
  meta_description TEXT,
  og_image TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);

CREATE TABLE IF NOT EXISTS marketing_contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name TEXT,
  email TEXT,
  phone TEXT,
  source TEXT NOT NULL DEFAULT 'manual',
  email_opt_in BOOLEAN NOT NULL DEFAULT false,
  whatsapp_opt_in BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

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

CREATE TABLE IF NOT EXISTS campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  channel TEXT NOT NULL DEFAULT 'email',
  status TEXT NOT NULL DEFAULT 'draft',
  subject TEXT,
  content TEXT,
  template JSONB NOT NULL DEFAULT '{}'::jsonb,
  segment_id UUID,
  scheduled_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS campaign_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  recipient_email TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'sent',
  sent_at TIMESTAMPTZ,
  opened_at TIMESTAMPTZ,
  clicked_at TIMESTAMPTZ,
  converted_at TIMESTAMPTZ,
  booking_id UUID REFERENCES bookings(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS message_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name TEXT NOT NULL DEFAULT 'Untitled Template',
  channel TEXT NOT NULL DEFAULT 'email',
  subject TEXT,
  content TEXT NOT NULL DEFAULT '',
  variables JSONB NOT NULL DEFAULT '[]'::jsonb,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS message_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
  template_id UUID REFERENCES message_templates(id) ON DELETE SET NULL,
  channel TEXT NOT NULL DEFAULT 'email',
  source TEXT NOT NULL DEFAULT 'messaging',
  recipient_name TEXT,
  recipient_email TEXT,
  recipient_phone TEXT,
  subject TEXT,
  content TEXT,
  status TEXT NOT NULL DEFAULT 'logged',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS maintenance_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  room_id UUID REFERENCES rooms(id) ON DELETE SET NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  priority VARCHAR(20) NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
  status VARCHAR(20) NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
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
  amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
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
  role VARCHAR(50) NOT NULL DEFAULT 'staff'
    CHECK (role IN ('manager', 'front_desk', 'housekeeping', 'maintenance', 'staff')),
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
  guests INTEGER NOT NULL DEFAULT 1 CHECK (guests > 0),
  status VARCHAR(20) NOT NULL DEFAULT 'waiting'
    CHECK (status IN ('waiting', 'notified', 'booked', 'expired')),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (check_out > check_in)
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_subdomain_lower
  ON tenants (lower(subdomain)) WHERE subdomain IS NOT NULL AND btrim(subdomain) <> '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_domain_lower
  ON tenants (lower(domain)) WHERE domain IS NOT NULL AND btrim(domain) <> '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_primary_hostname_lower
  ON tenants (lower(primary_hostname))
  WHERE primary_hostname IS NOT NULL AND btrim(primary_hostname) <> '';

CREATE INDEX IF NOT EXISTS idx_profiles_tenant ON profiles (tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_user_tenant ON user_roles (user_id, tenant_id);
CREATE INDEX IF NOT EXISTS idx_room_categories_tenant ON room_categories (tenant_id);
CREATE INDEX IF NOT EXISTS idx_rooms_tenant_status ON rooms (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_guest_profiles_tenant_created
  ON guest_profiles (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_guest_profiles_tenant_email
  ON guest_profiles (tenant_id, lower(email)) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bookings_tenant_created
  ON bookings (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bookings_tenant_dates
  ON bookings (tenant_id, check_in, check_out);
CREATE INDEX IF NOT EXISTS idx_bookings_room_dates
  ON bookings (room_id, check_in, check_out);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_external_uid
  ON bookings (tenant_id, room_id, external_uid) WHERE external_uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_booking_payments_tenant_received
  ON booking_payments (tenant_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_tenant_unread
  ON notifications (tenant_id, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_created
  ON audit_logs (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_waitlist_tenant_status
  ON waitlist (tenant_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_maintenance_tenant
  ON maintenance_requests (tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_expenses_tenant_date
  ON expenses (tenant_id, expense_date DESC);
CREATE INDEX IF NOT EXISTS idx_staff_tenant ON staff_members (tenant_id, is_active);
CREATE INDEX IF NOT EXISTS idx_channels_tenant ON channels (tenant_id);
CREATE INDEX IF NOT EXISTS idx_channels_room ON channels (room_id);
CREATE INDEX IF NOT EXISTS idx_message_templates_tenant_channel
  ON message_templates (tenant_id, channel);
CREATE INDEX IF NOT EXISTS idx_message_logs_tenant_created
  ON message_logs (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaigns_tenant_created
  ON campaigns (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_marketing_contacts_tenant
  ON marketing_contacts (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_marketing_segments_tenant_active
  ON marketing_segments (tenant_id, is_active, updated_at DESC);

DROP TRIGGER IF EXISTS update_tenants_updated_at ON tenants;
CREATE TRIGGER update_tenants_updated_at
  BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_profiles_updated_at ON profiles;
CREATE TRIGGER update_profiles_updated_at
  BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_room_categories_updated_at ON room_categories;
CREATE TRIGGER update_room_categories_updated_at
  BEFORE UPDATE ON room_categories FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_rooms_updated_at ON rooms;
CREATE TRIGGER update_rooms_updated_at
  BEFORE UPDATE ON rooms FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_pricing_rules_updated_at ON room_pricing_rules;
CREATE TRIGGER update_pricing_rules_updated_at
  BEFORE UPDATE ON room_pricing_rules FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_guest_profiles_updated_at ON guest_profiles;
CREATE TRIGGER update_guest_profiles_updated_at
  BEFORE UPDATE ON guest_profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_bookings_updated_at ON bookings;
CREATE TRIGGER update_bookings_updated_at
  BEFORE UPDATE ON bookings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_invoices_updated_at ON invoices;
CREATE TRIGGER update_invoices_updated_at
  BEFORE UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_pages_updated_at ON pages;
CREATE TRIGGER update_pages_updated_at
  BEFORE UPDATE ON pages FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_marketing_segments_updated_at ON marketing_segments;
CREATE TRIGGER update_marketing_segments_updated_at
  BEFORE UPDATE ON marketing_segments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_campaigns_updated_at ON campaigns;
CREATE TRIGGER update_campaigns_updated_at
  BEFORE UPDATE ON campaigns FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_message_templates_updated_at ON message_templates;
CREATE TRIGGER update_message_templates_updated_at
  BEFORE UPDATE ON message_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_maintenance_updated_at ON maintenance_requests;
CREATE TRIGGER update_maintenance_updated_at
  BEFORE UPDATE ON maintenance_requests FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_expenses_updated_at ON expenses;
CREATE TRIGGER update_expenses_updated_at
  BEFORE UPDATE ON expenses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_staff_updated_at ON staff_members;
CREATE TRIGGER update_staff_updated_at
  BEFORE UPDATE ON staff_members FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_waitlist_updated_at ON waitlist;
CREATE TRIGGER update_waitlist_updated_at
  BEFORE UPDATE ON waitlist FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_channels_updated_at ON channels;
CREATE TRIGGER update_channels_updated_at
  BEFORE UPDATE ON channels FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE FUNCTION mark_room_dirty_after_checkout()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.status = 'completed' AND OLD.status IS DISTINCT FROM 'completed' THEN
    UPDATE rooms SET housekeeping_status = 'dirty' WHERE id = NEW.room_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_mark_room_dirty ON bookings;
CREATE TRIGGER trigger_mark_room_dirty
  AFTER UPDATE ON bookings FOR EACH ROW EXECUTE FUNCTION mark_room_dirty_after_checkout();

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'bookings_prevent_overlap'
  ) THEN
    ALTER TABLE bookings
      ADD CONSTRAINT bookings_prevent_overlap
      EXCLUDE USING gist (
        tenant_id WITH =,
        room_id WITH =,
        daterange(check_in, check_out, '[)') WITH &&
      )
      WHERE (status IN ('pending', 'confirmed'));
  END IF;
END
$$;
