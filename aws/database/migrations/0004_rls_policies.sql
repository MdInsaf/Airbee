-- Row-Level Security (RLS) policies for multi-tenant isolation.
-- RLS is a second layer of defense: even if application SQL is missing WHERE tenant_id,
-- PostgreSQL prevents unauthorized access.

-- Enable RLS on all tenant-scoped tables
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE guests ENABLE ROW LEVEL SECURITY;
ALTER TABLE housekeeping ENABLE ROW LEVEL SECURITY;
ALTER TABLE room_pricing_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE marketing_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE marketing_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE marketing_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_templates ENABLE ROW LEVEL SECURITY;

-- Set tenant context in transaction (called by Django middleware)
-- SET app.tenant_id TO '<uuid>';

-- Bookings: users see only their tenant's bookings
DROP POLICY IF EXISTS rls_bookings ON bookings;
CREATE POLICY rls_bookings ON bookings
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Rooms: users see only their tenant's rooms
DROP POLICY IF EXISTS rls_rooms ON rooms;
CREATE POLICY rls_rooms ON rooms
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Guests: users see only guests from their tenant's bookings
DROP POLICY IF EXISTS rls_guests ON guests;
CREATE POLICY rls_guests ON guests
  USING (
    id IN (
      SELECT DISTINCT guest_id FROM bookings
      WHERE tenant_id = current_setting('app.tenant_id')::uuid
    )
  );

-- Housekeeping: only their tenant's rooms
DROP POLICY IF EXISTS rls_housekeeping ON housekeeping;
CREATE POLICY rls_housekeeping ON housekeeping
  USING (
    room_id IN (
      SELECT id FROM rooms
      WHERE tenant_id = current_setting('app.tenant_id')::uuid
    )
  );

-- Room pricing rules: only their tenant's rules
DROP POLICY IF EXISTS rls_room_pricing_rules ON room_pricing_rules;
CREATE POLICY rls_room_pricing_rules ON room_pricing_rules
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Channels: only their tenant's channels
DROP POLICY IF EXISTS rls_channels ON channels;
CREATE POLICY rls_channels ON channels
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Marketing contacts: only their tenant's contacts
DROP POLICY IF EXISTS rls_marketing_contacts ON marketing_contacts;
CREATE POLICY rls_marketing_contacts ON marketing_contacts
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Marketing segments: only their tenant's segments
DROP POLICY IF EXISTS rls_marketing_segments ON marketing_segments;
CREATE POLICY rls_marketing_segments ON marketing_segments
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Marketing campaigns: only their tenant's campaigns
DROP POLICY IF EXISTS rls_marketing_campaigns ON marketing_campaigns;
CREATE POLICY rls_marketing_campaigns ON marketing_campaigns
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Message templates: only their tenant's templates
DROP POLICY IF EXISTS rls_message_templates ON message_templates;
CREATE POLICY rls_message_templates ON message_templates
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
