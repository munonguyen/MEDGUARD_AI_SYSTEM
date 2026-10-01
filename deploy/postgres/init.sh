#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v app_password="$MEDGUARD_DB_PASSWORD" <<'SQL'
CREATE ROLE medguard LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /schema/rls_schema.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /schema/browser_schema.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
INSERT INTO tenants(tenant_id,name) VALUES ('tenant-demo','Platform organization') ON CONFLICT DO NOTHING;
GRANT USAGE ON SCHEMA public TO medguard;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO medguard;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO medguard;
REVOKE ALL ON api_keys FROM medguard;
SQL
