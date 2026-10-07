# MEDGUARD AI SYSTEM

MedGuard AI is an independent, schema-first clinical safety service with a chat-first React workspace for triage, medication safety, prescription OCR orchestration, medication reminders, product QR verification, follow-up, monitoring, pharmacy fulfillment, queue prioritization and result delivery.

This repository contains an end-to-end **development implementation** of the architecture in `MEDGUARD_AI_SYSTEM_OVERVIEW.docx` and the optimized architecture proposal. It is suitable for API integration demos, contract testing and architectural validation. It is **not clinically validated production software** and does not replace a doctor, pharmacist or emergency service.

## Current Scope

- FastAPI service with versioned `/v1` endpoints and generated OpenAPI schema.
- Chat-first React clinical workspace served by FastAPI, with natural-language intent routing, grounded conversational prose, compact inline citations, image attachment, QR camera/image scanning, durable history and responsive desktop/mobile behavior.
- Optional personal Profile with an explicit save/clear workflow. Development profiles persist locally per tenant; users can chat without creating one.
- Deterministic chat orchestration over the domain services; the conversation layer cannot override clinical safety rules.
- Optional two-agent answer pipeline routed through one LiteLLM gateway: an answer role analyzes the latest question and searches authoritative sources, then an isolated verifier role independently searches and evaluates the candidate before a deterministic release gate.
- LLM control plane for deterministic intent-risk classification, pre-call token limits, role output caps, HMAC-isolated exact-cache scopes, safe-request single-flight and bounded internal metrics. Clinical and personalized requests remain `no-store`.
- Separate Training Plane with governed Answer/Verifier contracts, PII/provenance/review checks, group-safe splits, dataset/evaluation gates, QLoRA templates, checksum-bound model registry and static vLLM candidate serving. No expert model is currently approved.
- Tenant-scoped chat conversations/messages and medication schedules, persisted in SQLite or PostgreSQL with RLS policies.
- Medication reminders created from natural language or from OCR directions only after completed human review.
- QR verification against a versioned development registry. A registry match is not proof of the physical authenticity of a product.
- `X-API-Key` + `X-Tenant-Id` authentication and tenant-scoped state.
- Required `Idempotency-Key` for every protected `POST`.
- Tenant-aware rate limiting with bounded development state and an atomic Redis production backend.
- Browser/API security headers, non-cacheable clinical API responses and bounded request IDs.
- Request ID propagation, standardized errors and append-only database-backed audit events.
- Durable repositories for OCR jobs and atomically reserved idempotent responses, with SQLite file mode for restart testing and PostgreSQL/RLS for production.
- Reliable Redis queue semantics using pending, processing and dead-letter lists with stale-claim recovery.
- **Versioned structured knowledge base** (`app/knowledge/`) with SHA-256 integrity verification:
  - `drug_interactions.json` — 10 drug-drug interaction pairs with severity tiers (HARD_STOP/SOFT_STOP)
  - `allergy_cross_matrix.json` — 7 allergy cross-reactivity groups with partial cross-reactivity
  - `red_flag_protocols.json` — 7 emergency red-flag patterns, 4 vital sign thresholds, 13 specialty routing rules
  - `contraindications.json` — 6 condition-based contraindication groups
  - `monitoring_rules.json` — metric-aware thresholds, trend direction semantics and minimum sample policy
  - `product_registry.json` — development product/serial/lot records for fail-closed QR matching
- Knowledge-backed deterministic triage with Vietnamese red-flag patterns, vital-sign thresholds, and routing to 13 specialties (Cardiology, Neurology, GI, Pulmonology, Orthopedics, Urology, Dermatology, Ophthalmology, ENT, OB-GYN, Pediatrics, Endocrinology, Psychiatry).
- Knowledge-backed medication safety checks: allergy cross-reactivity, drug-drug interactions, condition contraindications, duplicate active ingredients.
- Deterministic queue, follow-up, monitoring and pharmacy adapters.
- Result-delivery envelope preparation with development HMAC webhook signing.
- Asynchronous prescription extraction boundary with size/type validation, SHA-256 fingerprinting and tenant-scoped job polling.
- Uploads are written to the active object store and queued through the active queue adapter before a worker claims them.
- Fail-closed OCR worker: without a configured OCR backend, a claimed job becomes `failed` with `ocr_worker_unavailable`; no fake prescription result is produced.
- `/v1/health/readiness` reports active infrastructure, OCR, secrets, consent and clinical-approval blockers without conflating liveness with production readiness.
- Development model registry and circuit-breaker status endpoint.
- Every API response includes `trace` with `knowledge_version` and `knowledge_integrity` for audit reproducibility.

## Run

```bash
cd MEDGUARD_AI_SYSTEM
.venv/bin/uvicorn app.main:app --reload
```

The service is then available at `http://127.0.0.1:8000`. OpenAPI is available at `/docs` and `/openapi.json`.

The React production bundle is already emitted to `app/static/`, so the clinical workspace is available at `http://127.0.0.1:8000/`. For frontend development and rebuilding:

```bash
cd frontend
npm install
npm run dev
npm run build
```

Vite proxies `/v1` and `/metrics` to FastAPI at port `8000`. The production build uses the same origin as FastAPI, avoiding a second API base URL or browser credential boundary.

The development proxy preserves the browser-facing `Host` (`changeOrigin: false`)
so the backend can compare it with `Origin` on login and other state-changing
requests. Restart Vite after updating its configuration. If
`MEDGUARD_PUBLIC_ORIGIN` is explicitly set, it must match the URL opened in the
browser, including scheme and port. Production requires the configured HTTPS
public origin; do not disable Origin/CSRF checks or trust arbitrary forwarded
headers to resolve a development mismatch.

Authentication is restored only from the server session cookie (`HttpOnly`,
`SameSite=Strict`, and `Secure` in production), with existing absolute and idle
expiry. Passwords are never saved by the application in browser storage. Older
`medguard.auth.remember` records are removed on page initialization; expired
sessions require login again.

Run the real development-proxy browser regression with a free backend port 8000
and Vite test port 5295:

```bash
MEDGUARD_TEST_PYTHON=/path/to/python CHROME_PATH=/path/to/chromium npm --prefix frontend run test:auth-proxy
```

This uses an isolated temporary account database and synthetic accounts. It
checks both localhost and 127.0.0.1, login/reload/logout, cookie restrictions,
legacy password cleanup, and rejection of cross-origin and invalid-CSRF writes.


To exercise restart persistence locally, set `MEDGUARD_SQLITE_PATH=./var/medguard.sqlite3`. The default remains isolated in-memory SQLite for tests and short development runs.

Development credentials:

```text
tenant-demo / demo-key
tenant-alt  / alt-key
```

For webhook signing, set `MEDGUARD_DELIVERY_HMAC_SECRET` before starting the service. The built-in default is intentionally development-only.

Answer agents default to `disabled`. Provider credentials live only inside LiteLLM; the MedGuard process receives one budgeted virtual key, a gateway URL and two logical aliases. Start with `MEDGUARD_AGENT_MODE=shadow` so the models cannot change user-visible answers, then move to `enforced` only after live contract, citation, clinical, privacy, cost and latency evaluation. See [`docs/LLM_GATEWAY.md`](docs/LLM_GATEWAY.md).

Agent providers, model IDs, prompts, intermediate analysis, search queries and fallback diagnostics remain server-confidential. They are excluded from chat JSON, history and OpenAPI. The user interface exposes only a neutral verification assurance, quality scores and inspectable final sources.

## Example Request

```bash
# Triage with specialty routing
curl -X POST http://127.0.0.1:8000/v1/triage \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-key' \
  -H 'X-Tenant-Id: tenant-demo' \
  -H 'Idempotency-Key: triage-demo-001' \
  -d '{"patient_ref":"patient-demo-001","symptoms_text":"đau ngực và khó thở","locale":"vi-VN"}'

# Medication safety check
curl -X POST http://127.0.0.1:8000/v1/medication/safety-check \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-key' \
  -H 'X-Tenant-Id: tenant-demo' \
  -H 'Idempotency-Key: safety-demo-001' \
  -d '{
    "patient_ref":"patient-demo-001",
    "allergies":[{"substance":"penicillin","severity":"HIGH"}],
    "conditions":["loét dạ dày"],
    "current_medications":[{"name":"Warfarin","active_ingredient":"warfarin"}],
    "proposed_medications":[{"name":"Aspirin","active_ingredient":"aspirin"},{"name":"Ibuprofen","active_ingredient":"ibuprofen"}]
  }'
```

## Verify

```bash
.venv/bin/pytest -q
.venv/bin/python -m compileall -q app
.venv/bin/python scripts/run_all_benchmarks.py
.venv/bin/python scripts/validate_external_datasets.py
.venv/bin/python scripts/benchmark_mimic_ed.py
.venv/bin/python scripts/benchmark_chat_hard.py
.venv/bin/python scripts/benchmark_llm_control_plane.py --iterations 2000 --workers 20
.venv/bin/python scripts/validate_training_plane.py
.venv/bin/python scripts/benchmark_runtime.py --iterations 100
.venv/bin/python scripts/continuous_validation.py --iterations 3 --profile development
cd frontend && npm run build && npm run test:ui
```

The regression suite covers authentication, optional-profile/anonymous chat, tenant isolation, grounded answer evidence/history, safe narrative rendering, gateway request contracts, agent release/fallback gates, provider-native search metadata, claim-source linkage, external-dataset integrity, short-symptom fallback routing, explicit negation, Vietnamese text without diacritics, versioned English red flags, refusal of personalized dosing, headache and abdominal guidance, bounded continuation context with explicit episode reset, chat-extracted triage vitals, natural-language medication schedules, reviewed-prescription reminders, QR registry states, idempotency conflicts, in-flight reservations and concurrent writes, database restart recovery, schema migration, atomic job claims, bounded request IDs, rate-limit isolation and fail-closed behavior, security headers, triage with specialty routing and vital severity, medication safety, queue ordering and race-safe reclaim, OCR failure/recovery, monitoring semantics, pharmacy ranking, webhook signing, infrastructure adapters, readiness and knowledge integrity.

The UI smoke test uses a real browser at `1440x1000` and `390x844`, verifies that the provider-neutral `MedGuard đang xử lý` state appears before the final answer, confirms that internal evidence and raw business-data panels stay hidden, exercises natural-language triage and inline citations, creates and reads two medication reminders, verifies a QR payload without overstating physical authenticity, checks chat history and audit data, rejects horizontal overflow/composer clipping, and fails on page or console errors. It requires Google Chrome at the default macOS path, or `CHROME_PATH` can point to another Chromium executable.

The benchmark runner intentionally exits non-zero for the production gate while DS-OCR image files or real OCR engines are unavailable. The JSON labels alone are not treated as OCR predictions. The licensed MIMIC-IV-ED demo is checksum-validated and reported separately as a distribution-shift probe; it is explicitly not a production clinical acceptance set. Use the development profile for repeatable local architecture validation; use the production profile only when every readiness dependency and real evaluation dataset is present.

## Knowledge Base

The `app/knowledge/` directory contains versioned JSON files that back all clinical-safety decisions. Each file has a `_meta` block with version, effective date, source references, and `approved_by` field. The `_meta.approved_by` field must be signed off by the appropriate clinical specialist before any production deployment.

The knowledge loader (`app/knowledge/loader.py`) computes SHA-256 digests for each file and embeds them in every API response trace, enabling full audit reproducibility.

## Architecture Notes

The service keeps deterministic clinical-risk resolution separate from the optional LLM/VLM layer. LiteLLM is the only runtime LLM boundary and maps role aliases to separately credentialed providers. The answer role may analyze, search and present approved claims; the verifier role independently evaluates grounding, safety, completeness and citation coverage. Neither model may decide emergency severity, medication risk or catalog identity. Low confidence, missing search metadata, untrusted sources, changed locked claims, timeout and provider failure fall back to the deterministic answer or explicit review/error state. Clinical and personalized requests set `no-cache` and `no-store`; only policy-approved exact-safe traffic may use short cache and single-flight with versioned, pseudonymous scope. Semantic response cache remains disabled for agentic traffic.

Production adapters for PostgreSQL/RLS, Redis-backed queues/rate limiting and S3 are implemented but require real services and integration evidence. A production deployment still needs approved OCR models and image data, external secret management, OpenTelemetry, verified retention controls, enforced consent and independent clinical/legal validation. See [`docs/ARCHITECTURE_FLOW.md`](docs/ARCHITECTURE_FLOW.md), [`docs/ARCHITECTURE_STATUS.md`](docs/ARCHITECTURE_STATUS.md) and [`docs/DEPLOYMENT_RUNBOOK.md`](docs/DEPLOYMENT_RUNBOOK.md).

Fine-tuning is an offline specialization path, not a knowledge database or Gateway replacement. See [`docs/TRAINING_PLANE.md`](docs/TRAINING_PLANE.md) for dataset governance, QLoRA, held-out evaluation, registry promotion and vLLM shadow-serving procedures.

## Repository Workflow

Development integrates through protected `develop`; production releases promote from `release/<version>` into protected `main`. Feature, test and documentation branches remain short-lived and use Conventional Commits. See [`docs/GIT_WORKFLOW.md`](docs/GIT_WORKFLOW.md) for branch bases, merge order, required checks, hotfix handling and the initial import stack.
