-- MedGuard AI Production Schema with PostgreSQL Row-Level Security (RLS)
-- Principle P1 & P2: Strict Multi-Tenancy & Ephemeral/Scoped Medical Data

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Tenants Table
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. API Keys Table (Argon2 / SHA-256 Hashed, supports key rotation)
CREATE TABLE IF NOT EXISTS api_keys (
    key_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    key_hash VARCHAR(128) NOT NULL UNIQUE,
    key_prefix VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active', -- 'active', 'rotating', 'revoked'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_api_keys_lookup ON api_keys(key_hash, status);

-- 3. Durable Append-Only Audit Events Table
CREATE TABLE IF NOT EXISTS audit_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id),
    request_id VARCHAR(64) NOT NULL,
    action VARCHAR(128) NOT NULL,
    payload_type VARCHAR(64) NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_req ON audit_events(tenant_id, request_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_created ON audit_events(tenant_id, created_at);

-- 4. Prescription Jobs Table
CREATE TABLE IF NOT EXISTS prescription_jobs (
    job_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id),
    request_id VARCHAR(64) NOT NULL,
    patient_ref VARCHAR(128) NOT NULL,
    image_sha256 VARCHAR(64) NOT NULL,
    image_size_bytes INTEGER NOT NULL,
    content_type VARCHAR(64) NOT NULL,
    catalog_ref VARCHAR(64),
    status VARCHAR(32) NOT NULL DEFAULT 'queued', -- 'queued', 'processing', 'completed', 'failed'
    review_status VARCHAR(32) NOT NULL DEFAULT 'PENDING_REVIEW',
    result JSONB,
    error_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_prescription_jobs_lookup ON prescription_jobs(tenant_id, job_id);
CREATE INDEX IF NOT EXISTS idx_prescription_jobs_status ON prescription_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_prescription_jobs_tenant_status ON prescription_jobs(tenant_id, status, created_at);

-- 5. Idempotency Records Table
CREATE TABLE IF NOT EXISTS idempotency_records (
    record_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id),
    idempotency_key VARCHAR(128) NOT NULL,
    endpoint VARCHAR(128) NOT NULL,
    response_code INTEGER NOT NULL,
    response_body JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_tenant_endpoint_idempotency UNIQUE(tenant_id, endpoint, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expiry ON idempotency_records(expires_at);

-- Forward-compatible migration for databases created before payload fingerprints.
ALTER TABLE idempotency_records
    ADD COLUMN IF NOT EXISTS payload_hash VARCHAR(64);
UPDATE idempotency_records
    SET payload_hash = repeat('0', 64)
    WHERE payload_hash IS NULL;
ALTER TABLE idempotency_records
    ALTER COLUMN payload_hash SET NOT NULL;
ALTER TABLE idempotency_records
    DROP CONSTRAINT IF EXISTS uq_tenant_idempotency;
ALTER TABLE idempotency_records
    DROP CONSTRAINT IF EXISTS idempotency_records_tenant_id_idempotency_key_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_idempotency_tenant_endpoint_key
    ON idempotency_records(tenant_id, endpoint, idempotency_key);

-- 6. Monitoring Records Table
CREATE TABLE IF NOT EXISTS monitoring_records (
    record_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id),
    patient_ref VARCHAR(128) NOT NULL,
    indicator VARCHAR(64) NOT NULL,
    value NUMERIC(10, 2) NOT NULL,
    unit VARCHAR(32) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_monitoring_patient ON monitoring_records(tenant_id, patient_ref, recorded_at);

-- 7. Followup Plans Table
CREATE TABLE IF NOT EXISTS followup_plans (
    plan_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id),
    patient_ref VARCHAR(128) NOT NULL,
    chief_complaint VARCHAR(255) NOT NULL,
    cadence_days INTEGER NOT NULL,
    review_date DATE NOT NULL,
    triggers_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_followup_patient ON followup_plans(tenant_id, patient_ref);


-- 8. Tenant-scoped Chat History
CREATE TABLE IF NOT EXISTS chat_conversations (
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id),
    conversation_id VARCHAR(128) NOT NULL,
    title VARCHAR(160) NOT NULL,
    patient_ref VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, conversation_id)
);
CREATE INDEX IF NOT EXISTS idx_chat_conversations_updated
    ON chat_conversations(tenant_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id VARCHAR(128),
    tenant_id VARCHAR(64) NOT NULL,
    conversation_id VARCHAR(128) NOT NULL,
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    intent VARCHAR(32),
    status VARCHAR(32),
    result_json JSONB,
    answer_json JSONB,
    answer_origin VARCHAR(32),
    verification_status VARCHAR(32),
    knowledge_approval VARCHAR(32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (tenant_id, conversation_id)
        REFERENCES chat_conversations(tenant_id, conversation_id) ON DELETE CASCADE
);
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS answer_json JSONB;
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS request_id VARCHAR(128);
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS answer_origin VARCHAR(32);
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS verification_status VARCHAR(32);
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS knowledge_approval VARCHAR(32);
CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation
    ON chat_messages(tenant_id, conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant_created
    ON chat_messages(tenant_id, created_at);

-- 9. Medication Reminder Schedule
CREATE TABLE IF NOT EXISTS medication_schedules (
    schedule_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id),
    patient_ref VARCHAR(128) NOT NULL,
    medication_name VARCHAR(255) NOT NULL,
    dosage_text VARCHAR(255),
    scheduled_at TIMESTAMPTZ NOT NULL,
    recurrence VARCHAR(32) NOT NULL DEFAULT 'once',
    source VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_medication_schedules_patient
    ON medication_schedules(tenant_id, patient_ref, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_medication_schedules_patient_status
    ON medication_schedules(tenant_id, patient_ref, status);

-- =========================================================================
-- ROW-LEVEL SECURITY (RLS) POLICIES
-- Enforce tenant isolation directly at the database engine level.
-- Even if an application query forgets 'WHERE tenant_id = ...', RLS restricts
-- access strictly to the session's 'app.current_tenant_id'.
-- =========================================================================

-- Enable RLS and force it for all roles (including table owners)
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;

ALTER TABLE prescription_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE prescription_jobs FORCE ROW LEVEL SECURITY;

ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_records FORCE ROW LEVEL SECURITY;

ALTER TABLE monitoring_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring_records FORCE ROW LEVEL SECURITY;

ALTER TABLE followup_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE followup_plans FORCE ROW LEVEL SECURITY;

ALTER TABLE chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_conversations FORCE ROW LEVEL SECURITY;

ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY;

ALTER TABLE medication_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE medication_schedules FORCE ROW LEVEL SECURITY;

-- Define Tenant Isolation Policies
DROP POLICY IF EXISTS tenant_isolation_audit ON audit_events;
CREATE POLICY tenant_isolation_audit ON audit_events
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_prescription ON prescription_jobs;
CREATE POLICY tenant_isolation_prescription ON prescription_jobs
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_idempotency ON idempotency_records;
CREATE POLICY tenant_isolation_idempotency ON idempotency_records
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_monitoring ON monitoring_records;
CREATE POLICY tenant_isolation_monitoring ON monitoring_records
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_followup ON followup_plans;
CREATE POLICY tenant_isolation_followup ON followup_plans
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_chat_conversations ON chat_conversations;
CREATE POLICY tenant_isolation_chat_conversations ON chat_conversations
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_chat_messages ON chat_messages;
CREATE POLICY tenant_isolation_chat_messages ON chat_messages
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_medication_schedules ON medication_schedules;
CREATE POLICY tenant_isolation_medication_schedules ON medication_schedules
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));
