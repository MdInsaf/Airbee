-- ============================================================
-- Local development seed data
-- Tenant ID: 00000000-0000-0000-0000-000000000001
-- This file is auto-run by Docker when the DB is first created
-- ============================================================

-- Tenant (the hotel)
INSERT INTO tenants (id, name, slug, subdomain, contact_email, contact_phone, address, currency, timezone)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'The Grand Airbee',
    'grand-airbee',
    'grand-airbee',
    'manager@airbee.local',
    '+91-9876543210',
    'Mumbai, India',
    'INR',
    'Asia/Kolkata'
) ON CONFLICT DO NOTHING;

-- Room categories
INSERT INTO room_categories (id, tenant_id, name, description) VALUES
    ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'Standard',  'Comfortable standard room'),
    ('00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001', 'Deluxe',    'Spacious deluxe room'),
    ('00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000001', 'Suite',     'Luxury suite with ocean view'),
    ('00000000-0000-0000-0000-000000000013', '00000000-0000-0000-0000-000000000001', 'Executive', 'Executive room for business')
ON CONFLICT DO NOTHING;

-- Rooms
INSERT INTO rooms (id, tenant_id, name, category_id, base_price, max_guests, status, housekeeping_status, amenities) VALUES
    ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'Room 101', '00000000-0000-0000-0000-000000000010', 2999, 2, 'available',   'clean',       '["WiFi","AC","TV"]'),
    ('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'Room 102', '00000000-0000-0000-0000-000000000010', 2999, 2, 'unavailable', 'dirty',       '["WiFi","AC","TV"]'),
    ('10000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', 'Room 103', '00000000-0000-0000-0000-000000000010', 2999, 2, 'available',   'clean',       '["WiFi","AC","TV"]'),
    ('10000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000001', 'Room 201', '00000000-0000-0000-0000-000000000011', 4999, 2, 'available',   'clean',       '["WiFi","AC","TV","Mini Bar"]'),
    ('10000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000001', 'Room 202', '00000000-0000-0000-0000-000000000011', 4999, 2, 'unavailable', 'in_progress', '["WiFi","AC","TV","Mini Bar"]'),
    ('10000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000001', 'Room 203', '00000000-0000-0000-0000-000000000011', 4999, 2, 'maintenance', 'dirty',       '["WiFi","AC","TV","Mini Bar"]'),
    ('10000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000001', 'Suite 301','00000000-0000-0000-0000-000000000012', 9999, 3, 'available',   'clean',       '["WiFi","AC","TV","Mini Bar","Jacuzzi","Balcony"]'),
    ('10000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000001', 'Suite 302','00000000-0000-0000-0000-000000000012', 9999, 3, 'unavailable', 'clean',       '["WiFi","AC","TV","Mini Bar","Jacuzzi","Balcony"]'),
    ('10000000-0000-0000-0000-000000000009', '00000000-0000-0000-0000-000000000001', 'Exec 401', '00000000-0000-0000-0000-000000000013', 6999, 2, 'available',   'clean',       '["WiFi","AC","TV","Work Desk","Coffee Machine"]'),
    ('10000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'Exec 402', '00000000-0000-0000-0000-000000000013', 6999, 2, 'available',   'clean',       '["WiFi","AC","TV","Work Desk","Coffee Machine"]')
ON CONFLICT DO NOTHING;

-- Guests
INSERT INTO guest_profiles (id, tenant_id, name, email, phone) VALUES
    ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'Arjun Sharma',  'arjun@example.com',  '+91-9000000001'),
    ('20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'Priya Mehta',   'priya@example.com',  '+91-9000000002'),
    ('20000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', 'Rahul Gupta',   'rahul@example.com',  '+91-9000000003'),
    ('20000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000001', 'Sarah Johnson', 'sarah@example.com',  '+1-5550000001'),
    ('20000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000001', 'Kavya Reddy',   'kavya@example.com',  '+91-9000000005')
ON CONFLICT DO NOTHING;

-- Bookings (mix of past and current)
INSERT INTO bookings (id, tenant_id, room_id, guest_id, guest_name, guest_email, check_in, check_out, status, total_amount, payment_status, guests) VALUES
    ('30000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001',
     '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000001',
     'Arjun Sharma', 'arjun@example.com', CURRENT_DATE, CURRENT_DATE + 3, 'confirmed', 8997, 'paid', 2),
    ('30000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001',
     '10000000-0000-0000-0000-000000000005', '20000000-0000-0000-0000-000000000002',
     'Priya Mehta', 'priya@example.com', CURRENT_DATE - 1, CURRENT_DATE + 2, 'confirmed', 24995, 'paid', 3),
    ('30000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001',
     '10000000-0000-0000-0000-000000000008', '20000000-0000-0000-0000-000000000005',
     'Kavya Reddy', 'kavya@example.com', CURRENT_DATE, CURRENT_DATE + 5, 'confirmed', 59995, 'paid', 2),
    ('30000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000001',
     '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000003',
     'Rahul Gupta', 'rahul@example.com', CURRENT_DATE + 2, CURRENT_DATE + 4, 'confirmed', 5998, 'unpaid', 1),
    ('30000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000001',
     '10000000-0000-0000-0000-000000000007', '20000000-0000-0000-0000-000000000004',
     'Sarah Johnson', 'sarah@example.com', CURRENT_DATE + 1, CURRENT_DATE + 3, 'confirmed', 19998, 'partial', 2),
    ('30000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000001',
     '10000000-0000-0000-0000-000000000004', '20000000-0000-0000-0000-000000000001',
     'Arjun Sharma', 'arjun@example.com', CURRENT_DATE - 30, CURRENT_DATE - 27, 'completed', 14997, 'paid', 2),
    ('30000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000001',
     '10000000-0000-0000-0000-000000000009', '20000000-0000-0000-0000-000000000002',
     'Priya Mehta', 'priya@example.com', CURRENT_DATE - 15, CURRENT_DATE - 12, 'completed', 20997, 'paid', 1),
    ('30000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000001',
     '10000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000005',
     'Kavya Reddy', 'kavya@example.com', CURRENT_DATE - 60, CURRENT_DATE - 55, 'completed', 16495, 'paid', 4)
ON CONFLICT DO NOTHING;
