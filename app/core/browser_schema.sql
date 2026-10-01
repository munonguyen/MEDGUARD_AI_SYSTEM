-- Shared account/session storage. Only the trusted application role may access these tables.
CREATE TABLE IF NOT EXISTS browser_accounts (
    account_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    tenant_id TEXT NOT NULL UNIQUE,
    consent_at DOUBLE PRECISION,
    profile_json TEXT NOT NULL DEFAULT '{}',
    created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS browser_sessions (
    token_hash TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES browser_accounts(account_id) ON DELETE CASCADE,
    expires_at DOUBLE PRECISION NOT NULL,
    idle_expires_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_browser_session_account ON browser_sessions(account_id);
CREATE TABLE IF NOT EXISTS browser_auth_attempts (
    bucket TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL,
    window_start DOUBLE PRECISION NOT NULL
);
