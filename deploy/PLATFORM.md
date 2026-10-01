# MedGuard account and transport platform

This stack adds two non-root API replicas behind Nginx HTTPS and `least_conn`, PostgreSQL account/history/session persistence, and Redis rate limits/queue storage. API, PostgreSQL and Redis have no host ports. TLS terminates at Nginx; internal Docker traffic is plaintext on a private network. Production clinical readiness remains a separate, fail-closed gate.

## Start an isolated staging stack

Create `deploy/tls/fullchain.pem` and `deploy/tls/privkey.pem` using certificates issued for your deployment hostname. The CI workflow uses an ephemeral self-signed localhost certificate solely for tests. Never use its `verify=False` client behavior in production.

Set `POSTGRES_ADMIN_PASSWORD`, `MEDGUARD_DB_PASSWORD`, `MEDGUARD_REDIS_PASSWORD`, `MEDGUARD_SECRET_MASTER_KEY`, and `MEDGUARD_DELIVERY_HMAC_SECRET` using distinct secret-manager values. Database/Redis passwords must be URL-safe. Set `BROWSER_ALLOWED_ORIGINS` to exact HTTPS origins. Registration is closed by default; opening it is an explicit deployment setting (`BROWSER_REGISTRATION_ENABLED=true`). Set the Nginx `server_name` and redirect destination to your domain (the checked-in configuration targets `localhost:8443`).

```sh
docker compose -f deploy/compose.platform.yml up -d --build --wait
docker compose -f deploy/compose.platform.yml exec nginx nginx -t
```

The initial PostgreSQL bootstrap runs only when the database volume is empty. Existing databases require a reviewed migration of `app/core/browser_schema.sql` using the migration role. The application role is not a superuser and cannot bypass medical-table RLS. Back up and restore-test volumes; `docker compose down -v` deletes them and is intended only for disposable CI.

## Account/session contract

- Passwords: Argon2id, 64 MiB, three iterations, two lanes; at least 12 characters, up to 128.
- Sessions: random 256-bit tokens; only SHA-256 digests are stored. HttpOnly, SameSite=Strict, Path=/ cookies; Secure in production. Absolute lifetime seven days, idle lifetime 30 minutes. Sessions rotate on login and revoke in the shared database on logout or logout-all.
- Mutations: exact Origin allowlist plus session-bound CSRF tokens. Login/registration require a trusted Origin. Public API-key integrations remain supported; browser cookies always take precedence and cannot acquire operator privileges by injecting API headers.
- Account namespace: chat, uploads and schedules use the authenticated account namespace. Patient accounts cannot invoke audit, queue, pharmacy fulfillment, FHIR export, result delivery or job review/process tools, including through chat intent routing.
- Health profiles live on the server. Browser storage holds presentation preferences only. Patient care consent does not authorize copying conversations into the model-training buffer; browser conversations are excluded from that buffer.
- Consent is explicit and revocable on the account; a supplied consent header cannot override a refusal. Existing stored history remains readable/deletable after revocation.
- Authentication attempts are atomically limited in PostgreSQL across replicas and additionally at the Nginx edge. Production API rate limiting requires Redis.

## Operations and remaining release requirements

`MEDGUARD_PLATFORM_DIAGNOSTICS=true` adds an instance identifier for isolated failover tests; leave it false for public deployments. `/metrics`, API documentation, readiness details and circuit diagnostics are blocked at the public edge. Collect these through a controlled internal operations path.

The sample stack intentionally defaults to `MEDGUARD_AGENT_MODE=disabled` for reproducible platform testing. This is not evidence that an external Writer/Reviewer works. Configure and separately validate the actual model gateway, clinical knowledge approval, object storage, OCR workers, consent/retention policy and release-evidence manifest before clinical use.

Not yet implemented: verified-email onboarding, password recovery, MFA/SSO, infrastructure-managed encryption at rest, off-host backups, a second edge node, PostgreSQL/Redis failover, and production load/SLO evidence. Two API replicas do not remove Nginx or database single points of failure. The private-network transport assumption must be reviewed for your environment; use upstream TLS/mTLS when internal networks are not trusted. Image tags are version-family pinned; production should pin approved digests and run vulnerability scans.

Acceptance is exercised in `.github/workflows/platform-quality.yml`: real HTTPS browser journeys, RLS-backed account history, shared sessions across both API replicas, Nginx config validation, restart/failover and cross-node logout revocation. The local account tests additionally cover account isolation, CSRF, expiration, fake consent and shared authentication throttles.
