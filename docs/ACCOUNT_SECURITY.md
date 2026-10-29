# MedGuard account security

This change adds browser accounts. It does not certify the complete application as production-ready. The clinical output promotion gate remains mandatory. Legacy service API keys continue to serve integrations; a browser session always takes precedence and never falls back to a service key when expired.

## Implemented controls

- Registration validates email, explicit consent and password length (12 characters minimum, 256 UTF-8 bytes maximum); client-supplied roles are rejected. New users are patients.
- Passwords use Argon2id (64 MiB, three iterations, two lanes). Unknown accounts also incur password verification. Password/reset/session secrets are excluded from audit records.
- Opaque 256-bit session credentials are hashed in a private SQLite database. Cookie is HttpOnly, SameSite=Strict, Path=/, Secure in production. Absolute expiry is eight hours; inactivity expiry is thirty minutes. Logout, per-device revocation, logout-all, password change/reset and MFA changes revoke sessions server-side.
- Authenticated writes require a session-bound CSRF token and reject cross-origin requests. CSRF token is encrypted at rest and stable across tabs. Browser credentials stay out of localStorage.
- Persistent auth throttles limit each IP/purpose and account login to ten requests/minute; sensitive reauthentication is limited per user. This is not a distributed edge/WAF solution.
- User account IDs create isolated data scopes. Patients cannot access audit, operations, job processing or pharmacist review. A patient may upload prescriptions and read owned jobs; backend ownership checks still apply. Production metrics require an admin account. No public role-elevation endpoint exists.
- MFA uses TOTP, encrypted enrollment secrets, thirty-second codes, one-step clock tolerance and an atomic replay guard. Ten hashed, single-use recovery codes are displayed once. A remaining recovery code plus password allows MFA disable or password change when the authenticator is lost. Password reset does not bypass MFA.
- Email verification and recovery tokens are hashed, purpose-bound, thirty-minute and single-use. Recovery tokens appear in URL fragments, which are removed after the app reads them. SMTP uses verified STARTTLS. Tests stub email; no real delivery has been demonstrated.
- Health profiles persist per account encrypted with Fernet, behind CSRF-protected writes. Browser profile data is not stored in localStorage for account users. Health data in the existing chat/storage subsystem still requires its separate production encryption and retention controls.

## Configuration

For development, run the existing app and register through the login page. A private development encryption key is generated beside the account database. Do not copy this key into production or commit account files. Preserve the key together with the database for development restarts.

Production startup requires:

```
MEDGUARD_ENVIRONMENT=production
MEDGUARD_PUBLIC_ORIGIN=https://medguard.example
MEDGUARD_AUTH_DATABASE=/persistent/private/accounts.sqlite3
MEDGUARD_AUTH_ENCRYPTION_KEY=<secret-managed Fernet key>
MEDGUARD_REQUIRE_VERIFIED_EMAIL=true
MEDGUARD_SMTP_HOST=<smtp host>
MEDGUARD_SMTP_PORT=587
MEDGUARD_SMTP_FROM=<verified sender>
MEDGUARD_SMTP_USER=<smtp identity>
MEDGUARD_SMTP_PASSWORD=<secret-managed credential>
```

Generate a Fernet key with `cryptography.fernet.Fernet.generate_key()` in a secure provisioning environment; do not place secrets in source control or logs. Mount a persistent private volume; enforce directory permissions and encrypted storage/backups. Terminate HTTPS at a correctly configured trusted proxy, preserve the public host, and restrict direct backend access. Missing SMTP configuration causes recovery/verification to return 503; production verification must not be disabled as a workaround. Replace demo service keys with separately provisioned credentials.

The SQLite implementation supports a single application deployment on a persistent local volume. A multi-node account service, shared throttling, key rotation/migration, encrypted backup/restore drills, HA and disaster recovery are not delivered or proven here. Never use independent copies of this database per replica. Provision privileged operators outside public registration through a reviewed administrative process; there is intentionally no self-service admin signup.

## Validation and remaining release gates

Run `pytest app/tests/test_accounts_security.py`, the full backend suite, frontend build, `tests/auth-security-ui.mjs`, `tests/ui-smoke.mjs`, and `tests/contextual-length-ui.mjs` against an actual local API. The login helper creates synthetic test accounts through the real API; it is not a runtime authentication bypass. Browser screenshots exclude enrollment secrets and recovery codes.

Scan the pinned Python requirements with pip-audit and the frontend lockfile with npm audit. A zero finding count covers known advisories at scan time, not unknown flaws. This work has no independent penetration test, real HTTPS deployment, real SMTP delivery, distributed-load proof, clinical sign-off, or competitor assessment. OIDC/SSO, passkeys, account deletion/consent withdrawal, organization-admin UX and account lifecycle administration are not yet implemented. Treat these as explicit product/operational gaps, not features silently claimed to exist.

References: OWASP Authentication Cheat Sheet, Session Management Cheat Sheet and CSRF Prevention Cheat Sheet. The report records source commit, test results, real browser evidence and remaining clinical/production blockers before any push.
