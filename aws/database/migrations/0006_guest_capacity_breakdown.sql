-- Split room capacity and booking headcount into adults/children.
-- max_guests / guests are kept as server-computed totals (adults + children)
-- so existing read-only consumers (reports, exports, dashboard stats, etc.)
-- keep working unchanged.

ALTER TABLE rooms ADD COLUMN IF NOT EXISTS max_adults INTEGER;
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS max_children INTEGER;

UPDATE rooms
SET max_adults = COALESCE(max_adults, GREATEST(max_guests, 1)),
    max_children = COALESCE(max_children, 0)
WHERE max_adults IS NULL OR max_children IS NULL;

ALTER TABLE rooms ALTER COLUMN max_adults SET NOT NULL;
ALTER TABLE rooms ALTER COLUMN max_adults SET DEFAULT 2;
ALTER TABLE rooms ALTER COLUMN max_children SET NOT NULL;
ALTER TABLE rooms ALTER COLUMN max_children SET DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'rooms_max_adults_check'
    ) THEN
        ALTER TABLE rooms ADD CONSTRAINT rooms_max_adults_check CHECK (max_adults > 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'rooms_max_children_check'
    ) THEN
        ALTER TABLE rooms ADD CONSTRAINT rooms_max_children_check CHECK (max_children >= 0);
    END IF;
END $$;

ALTER TABLE bookings ADD COLUMN IF NOT EXISTS adults INTEGER;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS children INTEGER;

UPDATE bookings
SET adults = COALESCE(adults, GREATEST(guests, 1)),
    children = COALESCE(children, 0)
WHERE adults IS NULL OR children IS NULL;

ALTER TABLE bookings ALTER COLUMN adults SET NOT NULL;
ALTER TABLE bookings ALTER COLUMN adults SET DEFAULT 1;
ALTER TABLE bookings ALTER COLUMN children SET NOT NULL;
ALTER TABLE bookings ALTER COLUMN children SET DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'bookings_adults_check'
    ) THEN
        ALTER TABLE bookings ADD CONSTRAINT bookings_adults_check CHECK (adults > 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'bookings_children_check'
    ) THEN
        ALTER TABLE bookings ADD CONSTRAINT bookings_children_check CHECK (children >= 0);
    END IF;
END $$;
