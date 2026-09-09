"""Initialize or upgrade the PostgreSQL schema and seed configured tenants."""

from __future__ import annotations

import sys
from os import getenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings


def initialize_database() -> int:
    database_url = getenv("MEDGUARD_MIGRATION_DATABASE_URL") or settings.database_url or ""
    if not database_url.startswith(("postgres://", "postgresql://")):
        print(
            "MEDGUARD_MIGRATION_DATABASE_URL or MEDGUARD_DATABASE_URL must point to PostgreSQL",
            file=sys.stderr,
        )
        return 2
    try:
        import psycopg
    except ImportError:
        print("Install requirements-production.txt before initializing PostgreSQL", file=sys.stderr)
        return 2

    schema = (BASE_DIR / "app" / "core" / "rls_schema.sql").read_text(encoding="utf-8")
    with psycopg.connect(database_url) as connection:
        connection.execute(schema, prepare=False)
        for tenant_id in settings.allowed_tenants:
            connection.execute(
                """
                INSERT INTO tenants (tenant_id, name, status)
                VALUES (%s, %s, 'active')
                ON CONFLICT (tenant_id) DO UPDATE SET
                    status = 'active', updated_at = NOW()
                """,
                (tenant_id, tenant_id),
            )
    print(f"PostgreSQL schema initialized; tenants={len(settings.allowed_tenants)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(initialize_database())
