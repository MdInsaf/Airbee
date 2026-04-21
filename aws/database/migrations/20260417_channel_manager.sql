-- Channel Manager: iCal-based OTA sync
-- Run this after schema.sql

CREATE TABLE channels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  platform TEXT NOT NULL DEFAULT 'other',
  room_id UUID REFERENCES rooms(id) ON DELETE CASCADE,
  ical_url TEXT,
  last_synced_at TIMESTAMPTZ,
  sync_status TEXT DEFAULT 'pending',
  sync_error TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_channels_tenant ON channels(tenant_id);
CREATE INDEX idx_channels_room ON channels(room_id);

-- Track which bookings came from which channel
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS source_channel TEXT DEFAULT 'direct';
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS external_uid TEXT;
