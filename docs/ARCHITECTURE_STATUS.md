# MedGuard AI Architecture Status

## Executive status

The executable project is a coherent development architecture with production infrastructure adapters, not a production or clinically validated system. Regression, deterministic safety rules, durable repository contracts, reliable queue semantics and fail-closed behavior are operational. Deployment evidence, real OCR evidence, external clinical approval and production security controls remain gated.

`GET /v1/health` answers only whether the process is alive. `GET /v1/health/readiness` is the source of truth for deployment readiness and currently returns `production_ready=false`.

## Executable architecture

```text
Offline Training Plane (isolated from patient-serving runtime)
governed data -> de-id/review -> Answer + Verifier QLoRA
              -> held-out gates -> signed registry -> static candidates

Client / HIS / Pharmacy
        |
        v
React chat workspace -> FastAPI /v1 boundary
  request-id -> tenant auth -> consent -> schema -> idempotency
        |
        +-> chat intent router -> conversation history -> medication calendar
        +-> QR decode -> versioned product registry
        +---------------- synchronous ----------------+
        |                                              |
        v                                              v
Deterministic domain services                 Versioned knowledge
triage | safety | monitoring | queue           SHA-256 + approval metadata
follow-up | pharmacy | delivery | FHIR
        |
        +-> bounded claims -> LLM control plane -> LiteLLM gateway
        |                     risk/token/cache       -> answer role -> verifier role
        |                     single-flight          -> deterministic release gate
        |
        +---------------- asynchronous ---------------+
        v
job metadata -> object storage -> job queue -> OCR worker
                                      |
                                      v
                           detector -> recognizer -> parser
                                      -> fail-closed catalog match
                                      -> pharmacist review

Cross-cutting: audit events | metrics | rate limiting | security headers | circuit breaker | readiness
```

The browser-facing layer is a React clinical workspace served from the same FastAPI origin. It is an API client only: clinical decisions, tenant isolation, idempotency, audit state and job transitions remain authoritative in the backend.

## Completed in this optimization pass

- Monitoring thresholds moved to a versioned knowledge snapshot. Critical latest values are never hidden by insufficient trend history.
- Trend semantics are metric-aware and filter measurement noise with per-metric deltas.
- Triage now distinguishes warning vital signs (`URGENT`) from critical vital signs (`EMERGENCY`).
- OCR sample boxes, sample text, synthetic source objects and default clinical field values were removed from runtime paths.
- Upload, object storage and queue are connected; workers consume the exact tenant/job message and fail explicitly when the source object or OCR engine is unavailable.
- Every protected state-changing route uses an idempotency key, including process, review and FHIR export.
- Job state, idempotent responses and audit events now use tenant-scoped database repositories and survive SQLite file restarts.
- PostgreSQL uses a bounded Psycopg connection pool and transaction-scoped `app.current_tenant_id`; the supplied schema enforces RLS.
- Redis uses atomic pending-to-processing claims, acknowledgement, race-safe stale-claim recovery, bounded attempts and a dead-letter list.
- Database-backed idempotency uses a short atomic reservation lease so concurrent API instances cannot execute the same key simultaneously.
- Job processing uses a database compare-and-set transition and fresh repository reads to prevent stale per-process caches from double-claiming work.
- The OCR worker accepts graceful shutdown, periodically reclaims abandoned claims and resumes a durable job left in `processing` after a worker crash.
- Production database, queue and storage paths fail closed instead of silently falling back to local memory.
- Configured API keys can be rotated and revoked without a fallback that re-enables revoked credentials.
- Readiness exposes database, queue, object storage, OCR engine, knowledge approval, secrets, tenant credential and consent blockers.
- Benchmark scripts run independently. OCR CER/WER become `NOT EVALUABLE` when real images are absent instead of reporting a fabricated 0% error rate.
- Continuous validation repeats regression and data gates to detect non-determinism.
- Runtime smoke benchmarking measures p50/p95 HTTP latency, error count and sequential throughput for triage, safety and monitoring.
- The React workspace exposes task-focused flows for all nine capabilities, uses the versioned API contracts directly, and includes desktop/mobile browser smoke coverage.
- The React workspace is now chat-first: natural-language intent selection, durable tenant-scoped history, image attachments, lazy-loaded ZXing QR scanning, medication-calendar drawer and compact patient context replace the primary form workflow.
- Personal Profile is optional and has explicit edit/save/clear behavior. Profile age, sex, medication, allergy and condition context improves rule input, while ordinary chat remains available without it.
- Explicit tool selection and specific intent phrases take priority; when neither exists, short symptom markers such as pain, fever, numbness, swelling or rash route to triage instead of an unsupported response. Truly ambiguous requests ask one neutral clarification question.
- Grounded answers now use deterministic narrative blocks for ChatGPT-like prose. Medical facts remain owned by versioned domain results; the presenter only joins approved fields and supplies exact, HTML-free emphasis spans.
- The optional answer pipeline uses separate research and verifier roles with provider-native search metadata. A deterministic gate rejects missing citations, untrusted domains, low verifier scores, unsupported claims and any changed locked clinical instruction.
- LiteLLM is now the sole runtime LLM boundary. The app uses one budgeted virtual key and fixed logical research/verifier aliases; provider credentials, physical model routing and cost accounting remain in the gateway deployment.
- The gateway stack includes PostgreSQL-backed key/spend metadata, Redis coordination and default-off exact caching, Prometheus metrics, health checks, bounded retries and RPM/TPM/budget controls. Clinical requests explicitly send `store=false`, `no-cache` and `no-store`.
- An application-side LLM control plane now classifies bounded intent risk, enforces pre-call token limits and role output caps, constructs HMAC-isolated cache/session scopes, permits only short exact cache for safe registry traffic and coalesces identical safe misses locally plus through Redis when available.
- LLM observability records role/risk/cache/status, stage latency, estimated or actual tokens, cached input tokens, policy blocks, quality rejection and coalescing outcomes without using provider, model, tenant, patient or prompt text as metric labels.
- LiteLLM now maps `medguard-answer` only to Gemini 3.1 Pro Preview and `medguard-verifier` only to GPT-5.6 Sol, with bounded retries, cooldown and per-key parallel limits. There is no cross-role fallback; either role failure keeps the deterministic result and rejects the model draft.
- Gateway bootstrap and probe scripts create a restricted backend key and exercise liveness/model aliases without patient data. Readiness fails closed when mandatory agents are not enforced or the gateway is unreachable.
- The licensed MIMIC-IV-ED demo is stored with its source license, manifest and official SHA-256 checksums. External integrity and exploratory triage metrics now run in every continuous-validation iteration and can never satisfy the production gate.
- While a request is in flight, the client exposes one provider-neutral status, `MedGuard đang xử lý`, for at least 1000 ms. The final response remains buffered until that state completes; provider names, model stages and internal progress remain server-confidential.
- The chat surface no longer renders the internal answer-evidence disclosure or raw business-result panel. Research citations remain available only as compact inline links attached to supported narrative claims.
- Headache requests receive versioned focused questions, bounded self-care and explicit safety-net guidance; sudden severe headache and headache after head trauma are escalated before narrative rendering.
- Chat history and medication schedules have SQLite/PostgreSQL repositories plus PostgreSQL RLS; idempotent chat replay does not duplicate messages.
- Natural-language reminders accept multiple times and daily recurrence. Confirmed OCR instructions create reminders with `source=prescription_review`; unreviewed or time-less OCR results fail closed.
- Product QR verification distinguishes registry match, suspected counterfeit, unknown, invalid and recalled states while explicitly avoiding a physical-authenticity claim.
- Tenant-aware rate limiting uses bounded expiring windows in development and atomic Redis counters in production; production fails closed if the distributed limiter is unavailable.
- Clinical API responses are non-cacheable, request IDs are bounded, browser responses receive CSP/frame/referrer/permissions protections and dynamic job URLs share stable metrics labels.
- Database engine optimized with WAL `synchronous = NORMAL`, 64MB memory page cache, memory temp store, 256MB mmap I/O, and targeted indexes on `audit_events(tenant_id, created_at)`, `prescription_jobs(tenant_id, status, created_at)`, `chat_messages(tenant_id, created_at)`, and `medication_schedules(tenant_id, patient_ref, status)` across SQLite and PostgreSQL RLS schemas.
- Knowledge store memoizes `version_string()` and `integrity_report()` snapshots to eliminate repeated allocations and sort operations on trace headers.
- Circuit breaker hardened with `threading.RLock` to eliminate race conditions under concurrent worker load.
- Continuous multi-threaded stress and stability test harness added (`scripts/continuous_stress_validation.py`) to systematically measure concurrency, throughput, latency percentiles, and determinism.
- A separate offline Training Plane now enforces incompatible Answer/Verifier schemas, source rights, de-identification checks, expert review, case-group splits, duplicate rejection, category coverage and SHA-256 dataset manifests. External MIMIC evaluation data is prohibited from entering training.
- Role-specific QLoRA runners train only approved `train` data, use `validation` during SFT and reserve `test` for independent safety gates. Placeholder models, floating revisions, incomplete datasets and checksum drift fail before GPU libraries load.
- Held-out evaluation must cover the exact role-specific test IDs and categories, then binds its report to the dataset SHA-256. Candidate promotion requires that SFT-approved dataset, intact adapter artifacts, a passing matching evaluation and authorized human approval. The offline registry never changes active LiteLLM routing automatically.
- Isolated vLLM candidate services use statically loaded adapters with runtime LoRA updates disabled. Self-hosted candidates remain ineligible for live routing until an independent retrieval contract satisfies the existing source and citation gate.
- Emergency triage narratives now use specialty-neutral safety language and preserve only the matched rule advice. A neurological emergency can no longer inherit cardiac summaries, questions or safety notes, and the interface no longer presents deterministic system output as a doctor's observation.
- Clinical phrase matching now respects explicit local negation and word boundaries, preventing `khong` from matching the respiratory keyword `ho` while preserving phrases such as `đau ngực không giảm`. Versioned emergency patterns also match Vietnamese text without diacritics and their existing English equivalents.
- The evaluation-only `DS-CHAT-HARD` suite adds 21 difficult chat cases across red flags, prompt injection, medication safety, dose refusal, monitoring, scheduling, QR verification and ambiguous abdominal discomfort. It runs in continuous validation but is explicitly prohibited from training and cannot establish clinical accuracy.
- Natural-language reminders with explicit medicine times route to schedules without requiring a tag. Requests for a personalized exact dose are rejected before any model call, and the assistant no longer represents itself as a doctor.
- Ambiguous descriptions such as `bụng cồn cào` now route directly to versioned digestive guidance instead of a generic fallback. The response asks focused location, timing, meal-relation, associated-symptom and red-flag questions without asserting a diagnosis.
- The React severity badge now depends only on structured urgency/risk fields. Safety-net prose containing the words `cấp cứu` cannot incorrectly relabel a `ROUTINE` result as `EMERGENCY`.
- Triage carries one bounded prior symptom turn only for explicit conversational continuations. Abdominal nausea updates retain the active episode, avoid asking whether already-reported nausea exists and ask instead about vomiting, oral hydration and associated warning signs; explicit new-request markers prevent stale symptom reuse.
- Routine answers render as continuous prose without status badges, workflow shortcut blocks or automatic suggestion chips. Structured `URGENT` and `EMERGENCY` warnings remain visually prominent.

## Current measured state

| Gate | Current result | Meaning |
|---|---|---|
| Python regression | 174 passed | Development contracts, fixed two-model role bindings, bounded multi-turn symptom context, hard-user chat behavior, Training Plane governance/promotion, LLM risk/token/cache isolation, fail-closed unknown intents, single-flight behavior and Redis degradation, LiteLLM-only runtime, external dataset integrity, provider adapters, routing, claim-source linkage, multi-agent rejection/fallback gates, narrative safety, grounded answers, optional-profile chat, history/schedules/QR, persistence, security and recovery regressions are green |
| React build and browser smoke | Pass | Provider-neutral loading before the final answer, conversational narrative, inline citations, hidden internal metadata, bounded emphasis, triage, schedules, QR, history and audit pass at 1440x1000 and 390x844 with overflow and composer bounds checks |
| Triage golden fixture | Kappa 0.944; under-triage 0%; emergency recall 100% | Passes current internally generated labels |
| Interaction fixture | Recall 100%; precision 100% | Passes current finite knowledge-backed fixture |
| Allergy fixture | Recall 100% | Passes current finite knowledge-backed fixture |
| Adversarial fixture | Fail-closed 100%; zero default catalog violations | Passes current generated stress cases |
| HTTP runtime smoke benchmark (300 requests) | 0 errors; 463.54 req/s; max endpoint p95 2.749 ms | Standalone runtime benchmark passes with negligible latency overhead across triage, safety, and monitoring |
| Continuous stress validation (1,125 requests, 20 workers, 5 cycles) | 0 errors (0.00%); p50 44.033 ms; p95 54.638 ms; p99 93.330 ms; max 117.113 ms | Proves architectural concurrency safety and deterministic outputs across 9 capabilities under sustained parallel load |
| LLM control-plane benchmark | PASS; 2,000 unique scopes; 0 collisions; policy p95 0.0349 ms; 20 callers to 1 operation | Verifies deterministic risk/cache scope construction and process-local request coalescing without making live model calls |
| Training-plane architecture gate | PASS; 11 controls | Verifies role isolation, QLoRA fail-closed templates, dataset/evaluation gates, static candidate serving, registry shape and exclusion of external evaluation data without claiming a trained model |
| Expert model readiness | False | No governed dataset, trained adapter, held-out predictions or authorized model approval exists; the candidate aliases remain outside active LiteLLM routing |
| Hard-user chat challenge | PASS; 21/21 cases | Development-only behavior checks pass for difficult phrasing, focused abdominal guidance, safety invariants and hidden provider internals; the set is not expert-adjudicated or production-evaluable |
| Continuous validation (3 runs) | PASS; p95 6.420-10.216 ms; 153 tests, 21/21 hard-user cases, LLM-control and Training Plane gates passed per run | Gateway/cache/training contracts and external checksums remained deterministic. OCR stays explicitly not evaluable and external triage remains a visible blocker |
| MIMIC-IV-ED demo integrity | PASS; 7 files; 222 triage rows; 207 labeled | Licensed, deidentified external demo is intact; it is an exploratory distribution-shift probe, not a production acceptance dataset |
| MIMIC-IV-ED demo triage probe | Emergency recall 24.35%; severe under-triage 33.82% | Versioned English red flags improve the exploratory signal, but generalization remains inadequate; production stays blocked and the result must not be tuned away without independent labels |
| Live LiteLLM agent evaluation | Not run | No populated gateway `.env` or MedGuard virtual key is present; request contracts are tested with protocol doubles, not live clinical evidence |
| OCR CER/WER | Not evaluable | All 300 referenced image files are absent |
| Production readiness | False | Development backends and approvals are still active |

These values measure repeatability against repository fixtures. They are not external clinical validation, prospective performance, real-world calibration or regulatory acceptance.

## Production blockers

1. Deploy and exercise PostgreSQL with the implemented pool/RLS schema; prove backup/restore and tenant isolation against a real service.
2. Deploy Redis with persistence and the implemented acknowledgement/reclaim/dead-letter worker flow; add operational dead-letter alerts.
3. Deploy encrypted object storage and collect lifecycle deletion evidence plus tenant authorization tests.
4. Install and pin real detector/recognizer models; add licensed, de-identified images for every DS-OCR label and preserve prediction artifacts.
5. Replace development credentials and secrets; enforce consent and connect to a verifiable consent-record system.
6. Obtain signed clinical approval for every knowledge snapshot and independently relabel the evaluation datasets.
7. Exercise the Redis rate limiter across multiple API replicas and validate limits against expected tenant traffic.
8. Add OpenTelemetry, SLO alerts, load/soak tests, disaster recovery and security testing.
9. Complete legal, privacy, hospital ethics and clinical workflow acceptance before any patient-facing use.
10. Replace the development review operation with authenticated clinician/pharmacist roles and approval evidence before reviewed OCR can create production reminders.
11. Replace browser-local development Profiles with authenticated user accounts, encrypted profile storage, consent records and profile-level authorization.
12. Run a deidentified shadow set through the live LiteLLM aliases, review citation correctness, fallback behavior, cost and calibration with clinicians before requiring agents in production.
13. Build an independently adjudicated Vietnamese/multilingual triage set that represents the intended population; resolve the MIMIC distribution-shift failure without training or tuning directly on the demo labels.
14. Validate both role failure paths, exact-cache hit isolation, distributed single-flight behavior, budget rejection and provider prompt-cache accounting against a deployed multi-replica LiteLLM environment.
15. Curate and independently review governed Answer and Verifier datasets that meet every role, split, category and class-coverage gate without using the MIMIC external probe as training data.
16. Resolve and freeze the training image, CUDA stack, base-model licenses and immutable revisions; then execute QLoRA and held-out evaluation on controlled GPU infrastructure.
17. Deploy approved candidates with independent retrieval, run deidentified shadow and calibrated A/B evaluation, obtain signed model-risk approval and prove rollback before changing any production alias.

## Validation commands

```bash
.venv/bin/pytest -q
.venv/bin/python -m compileall -q app scripts training
.venv/bin/python scripts/run_all_benchmarks.py
.venv/bin/python scripts/validate_external_datasets.py
.venv/bin/python scripts/benchmark_mimic_ed.py
.venv/bin/python scripts/benchmark_chat_hard.py
.venv/bin/python scripts/benchmark_llm_control_plane.py --iterations 2000 --workers 20
.venv/bin/python scripts/validate_training_plane.py
.venv/bin/python scripts/benchmark_runtime.py --iterations 100
.venv/bin/python scripts/continuous_validation.py --iterations 3 --profile development
.venv/bin/python scripts/continuous_validation.py --iterations 3 --profile production
cd frontend && npm run build && npm run test:ui
```

The development profile may pass while explicitly reporting OCR/readiness blockers. The production profile must remain red until all required infrastructure, evidence and approvals are present.
