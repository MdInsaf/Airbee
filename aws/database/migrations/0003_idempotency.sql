-- Durable request idempotency for booking and payment mutations.
-- The reservation and its business mutation are committed in one transaction,
-- so a competing Lambda either observes the completed response or becomes the
-- request owner if the first transaction rolls back.

CREATE TABLE IF NOT EXISTS api_idempotency_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  scope VARCHAR(255) NOT NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  response_status INTEGER,
  response_body JSONB,
  resource_type VARCHAR(100),
  resource_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '24 hours'),
  CONSTRAINT api_idempotency_keys_scope_key_unique
    UNIQUE (tenant_id, scope, idempotency_key),
  CONSTRAINT api_idempotency_keys_response_status_valid
    CHECK (response_status IS NULL OR response_status BETWEEN 200 AND 299)
);

CREATE INDEX IF NOT EXISTS idx_api_idempotency_keys_expiry
  ON api_idempotency_keys (expires_at);

