\set ON_ERROR_STOP on

-- Compatibility entry point for psql users.
-- The authoritative schema is the ordered migration sequence below.
\ir migrations/0001_foundation.sql
\ir migrations/0002_contract_alignment.sql
\ir migrations/0003_idempotency.sql
