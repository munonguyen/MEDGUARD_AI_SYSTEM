# Production Deployment Runbook

This runbook configures the implemented production adapters. Passing these infrastructure checks does not constitute clinical approval.

## 1. Prepare dependencies and secrets

```bash
.venv/bin/pip install -r requirements-production.txt
```

Set the variables shown in `.env.production.example` through the deployment platform's secret manager. Do not commit a populated `.env.production` file. `MEDGUARD_ALLOWED_TENANTS` and the keys of `MEDGUARD_API_KEYS_JSON` must match exactly.

Provision provider keys only in the LiteLLM deployment, never in the MedGuard API environment. Start the gateway stack, create a budgeted virtual key and assign only that key to `MEDGUARD_LLM_GATEWAY_API_KEY`:

```bash
cd infrastructure/litellm
cp .env.example .env
# Populate strong gateway/database/Redis secrets and restricted provider keys.
docker compose up -d
cd ../..
LITELLM_MASTER_KEY='<master-key>' .venv/bin/python scripts/bootstrap_litellm_key.py
MEDGUARD_LLM_GATEWAY_API_KEY='<virtual-key>' \
  .venv/bin/python scripts/check_llm_gateway.py --probe-models
```

Set the input/output token caps, prompt version, safe exact-cache TTL and single-flight timeout from `.env.production.example`. Keep `MEDGUARD_REDIS_URL` reachable from every API replica so exact-cache-safe misses can use the distributed coalescing lock. Loss of this optimization does not permit clinical caching or bypass the release gate.

Start the answer pipeline with `MEDGUARD_AGENT_MODE=shadow`, review verifier rejection reasons, citation validity, costs and latency, then promote to `enforced`. Never send raw patient identifiers to a model provider. The application redacts common references, email addresses and phone numbers, but deployment policy must still prevent free-text PHI from leaving an environment unless the providers and legal basis are approved for that processing.

When `MEDGUARD_AGENT_REQUIRED_FOR_PRODUCTION=true`, readiness requires a reachable gateway, a virtual key, both role aliases and `MEDGUARD_AGENT_MODE=enforced`. Physical model promotion and rollback occur behind aliases and must pass compatibility tests for structured output, provider-native search citations and the independent verifier contract. Test budget exhaustion, concurrency rejection, exact-cache isolation, Redis-lock recovery and each role failure before promotion. See `docs/LLM_GATEWAY.md` for the complete policy.

Self-hosted expert adapters are optional and governed by a separate Training Plane. Do not install training dependencies in the API image. Do not deploy `infrastructure/litellm/expert-models.candidate.yaml` until the dataset, held-out evaluation, artifact and human-approval checksums are registered. Serve approved adapters statically through `infrastructure/model-serving/docker-compose.yml`; runtime LoRA loading must remain disabled. Follow `docs/TRAINING_PLANE.md`.

Use separate PostgreSQL roles:

- A migration role in `MEDGUARD_MIGRATION_DATABASE_URL` with permission to create tables, policies and required extensions.
- A runtime role in `MEDGUARD_DATABASE_URL` with only the table privileges needed by the application.

## 2. Initialize PostgreSQL and RLS

```bash
.venv/bin/python scripts/init_database.py
```

The command applies `app/core/rls_schema.sql`, upgrades the idempotency fingerprint column and seeds the configured tenant IDs. Run it as a deployment job before starting API instances.

Verify tenant isolation with the runtime role. A transaction must set `app.current_tenant_id`, and queries to audit, job, idempotency, monitoring and follow-up tables must only return that tenant's rows.

## 3. Prepare Redis and object storage

Redis must support `BLMOVE` (Redis 6.2 or newer). The worker atomically moves messages from `pending` to `processing`, acknowledges completed work, retries stale claims and sends exhausted claims to `dead-letter`. The API also uses atomic Redis counters for tenant-aware rate limiting. Configure `MEDGUARD_RATE_LIMIT_REQUESTS` and `MEDGUARD_RATE_LIMIT_WINDOW_SECONDS` from measured tenant traffic; do not disable the limiter in production.

Create the configured S3 bucket before deployment. Require TLS, server-side encryption, restricted tenant key prefixes and a lifecycle policy that deletes prescription images within the approved retention window. The application performs `HeadBucket` during readiness but lifecycle deletion evidence must be checked outside the application.

## 4. Start API and worker processes

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
.venv/bin/python scripts/run_ocr_worker.py \
  --visibility-timeout-seconds 300 \
  --reclaim-interval-seconds 30
```

Run at least one worker separately from the API. The runner handles `SIGINT`/`SIGTERM`, periodically reclaims abandoned processing messages and supports `--once` for deployment smoke checks.

## 5. Deployment gates

```bash
curl --fail http://127.0.0.1:8000/v1/health
curl --fail http://127.0.0.1:8000/v1/health/readiness
.venv/bin/python scripts/continuous_validation.py --iterations 3 --profile production
.venv/bin/python scripts/validate_external_datasets.py
.venv/bin/python scripts/benchmark_mimic_ed.py
```

Do not route production traffic unless `production_ready=true` and the production validation profile passes. Independently verify backup/restore, Redis persistence, dead-letter alerts, rate-limit consistency across multiple API replicas, S3 lifecycle deletion, secret rotation, consent evidence, OCR model checksums, signed clinical approvals, agent shadow-set quality, citation validity, provider data controls and timeout/fallback behavior.

## 6. Rollback and recovery

- Stop new traffic before rolling back an incompatible schema or application version.
- Preserve PostgreSQL job, idempotency and audit tables. Never clear them through application code in production.
- Allow workers to finish claimed jobs or wait for the visibility timeout so another worker can reclaim them.
- Inspect and replay dead-letter messages only through an audited operator procedure.
- Restore PostgreSQL from a tested backup and verify RLS before reopening traffic.
