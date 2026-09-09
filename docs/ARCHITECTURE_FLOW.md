# MedGuard AI Architecture Flow

## 1. Source Of Truth

- `MEDGUARD_AI_SYSTEM_OVERVIEW.docx` defines the clinical-safety commitments and integration expectations.
- `OPTIMIZED_AI_HEALTHCARE_ARCHITECTURE_PROPOSAL.md` defines the independent-service architecture and release direction.
- `COMPREHENSIVE_AI_HEALTHCARE_MULTI_AGENT_AND_VISION_SYSTEM.md` and `FINAL_PROJECT_AI_HEALTHCARE_TOPIC_PROPOSAL.md` define the demo scope and the nine reusable capabilities.
- This repository is the executable development contract for the current implementation.

## 2. Service Boundary

MedGuard AI is an independent, versioned FastAPI service. It does not import or query a customer ORM/database. A customer sends the minimum tenant-scoped payload required for one operation and receives a schema-validated response.

The chat-first React clinical workspace is compiled into `app/static/` and served by FastAPI at `/`. In development, Vite proxies `/v1` and `/metrics` to FastAPI. Conversation history and medication reminders are backend-owned tenant data; transient composer and attachment preview state remain in React. The optional development Profile is explicitly saved to browser storage per tenant and can be cleared by the user. The UI never becomes a second source of truth for clinical decisions, jobs, identity, audit or idempotency.

Authentication and isolation are enforced at the boundary:

- `X-API-Key` identifies the credential.
- `X-Tenant-Id` selects the tenant namespace.
- `Idempotency-Key` is required on every protected `POST`.
- `X-Request-Id` is generated or preserved for tracing.
- Invalid or oversized request IDs are replaced, and protected API routes are rate-limited by tenant or client identity.
- Jobs, chat history, medication schedules, audit events and idempotency entries are persisted and keyed by tenant.
- The API accepts `patient_ref`, not direct personal identifiers.

The database layer uses SQLite in development and a PostgreSQL connection pool with transaction-scoped tenant context in production. PostgreSQL RLS policies provide a second isolation boundary beneath repository tenant filters.

### Offline Training Plane

Training is isolated from the request path. Governed data must pass de-identification, usage-rights confirmation, expert review, normalized duplicate detection and case-group split assignment before a SHA-256 dataset manifest can be approved for SFT. Answer and Verifier use different schemas, targets and evaluation metrics. External evaluation sources such as the MIMIC-IV-ED demo are rejected from training.

Role-specific QLoRA adapters are trained only from train/validation splits. The test split remains held out for safety evaluation. Artifact, dataset, evaluation and human-approval checksums bind a model version in the offline registry. Static vLLM candidates remain outside active LiteLLM aliases until a deidentified shadow evaluation passes. Training never changes deterministic rules, knowledge snapshots or live routing automatically. See `docs/TRAINING_PLANE.md`.

## 3. Endpoint Inventory

| Method | Endpoint | Flow | Current behavior |
|---|---|---|---|
| `GET` | `/v1/health` | Sync | Service liveness response |
| `GET` | `/v1/health/readiness` | Sync | Evidence-based production dependency checks |
| `GET` | `/v1/models` | Sync | Active model/rule registry descriptors |
| `GET` | `/v1/health/circuit-status` | Sync | Model-provider circuit snapshot |
| `POST` | `/v1/chat` | Sync | Deterministic domain dispatch plus optional two-agent researched-answer pipeline |
| `GET/DELETE` | `/v1/chat/conversations[/{id}]` | Sync | Tenant-scoped conversation history and deletion |
| `POST` | `/v1/triage` | Sync | Knowledge-backed red flags, vitals, specialty routing, ESI, advice |
| `POST` | `/v1/medication/safety-check` | Sync | Knowledge-backed allergy, interaction, contraindication and duplicate checks |
| `POST` | `/v1/queue/prioritize` | Sync | Deterministic queue ordering |
| `POST` | `/v1/followup/plan` | Sync | Rule-backed follow-up suggestions or explicit `unknown` |
| `POST` | `/v1/monitoring/ingest` | Sync | Threshold and trend analysis with escalation |
| `POST` | `/v1/pharmacy/fulfillment` | Sync | Development branch ranking adapter |
| `POST` | `/v1/result-delivery/prepare` | Sync | Webhook/SSE/notification envelope preparation |
| `POST` | `/v1/prescription/extract` | Async | Accepts image metadata and returns `202` plus `job_id` |
| `GET` | `/v1/medication-schedules` | Sync | Tenant/patient-scoped medication reminder calendar |
| `POST` | `/v1/product/verify` | Sync | Product, serial and lot comparison with the versioned registry |
| `GET` | `/v1/jobs/{job_id}` | Sync poll | Tenant-scoped OCR job status |
| `POST` | `/v1/jobs/{job_id}/process` | Dev operation | Idempotent single-job processing trigger |
| `POST` | `/v1/jobs/{job_id}/review` | Dev operation | Idempotent completed-job review transition |
| `GET` | `/v1/audit/events` | Sync | Tenant-scoped development audit view |
| `POST` | `/v1/fhir/export` | Sync | Idempotent FHIR R4 bundle adapter |

## 4. Structured Knowledge Base

All clinical-safety decisions are backed by versioned, SHA-256 verified knowledge files stored in `app/knowledge/`:

| File | Contents | Entries |
|---|---|---|
| `drug_interactions.json` | Drug-drug interaction pairs with severity, tier (HARD_STOP/SOFT_STOP), mechanism, recommendation | 10 pairs |
| `allergy_cross_matrix.json` | Allergy cross-reactivity groups with primary allergen, cross-reactive and partial cross-reactive substances | 7 groups |
| `red_flag_protocols.json` | Emergency red-flag patterns, vital sign thresholds, specialty routing rules | 7 patterns + 4 vitals + 13 specialties |
| `contraindications.json` | Condition-based contraindications with medication groups and recommendations | 6 groups |
| `monitoring_rules.json` | Monitoring thresholds, per-metric noise deltas and trend semantics | 7 metrics |
| `product_registry.json` | Development product, GTIN, serial, lot and recall records | 3 fixtures |

### Knowledge integrity

Every API response includes a `trace` object with:
- `knowledge_version`: composite version string of all knowledge files
- `details.knowledge_integrity`: per-file SHA-256 digest and version

This allows audit systems to verify exactly which knowledge snapshot was used for each clinical decision.

### Knowledge loader

`app/knowledge/loader.py` loads all JSON knowledge files once at import time and makes them available through typed accessors. The loader verifies SHA-256 integrity and exposes `version_string()` and `integrity_report()` for embedding in trace/audit metadata.

## 5. Synchronous Flow

```text
Customer system
    -> HTTPS request with tenant credentials and idempotency key
    -> FastAPI middleware assigns request_id
    -> Pydantic validates the request schema
    -> tenant/auth dependency verifies the credential pair
    -> durable idempotency repository returns a prior response or detects conflict
    -> explicit domain service executes deterministic rules backed by versioned knowledge
    -> response includes request_id, disclaimer, trace with knowledge_version and integrity
    -> append-only database-backed audit event
```

The synchronous domain operations are triage, medication safety, queue prioritization, follow-up planning, monitoring, pharmacy fulfillment and result-delivery preparation. The current implementation does not allow an LLM to override the deterministic medical-risk result.

### Chat orchestration

`POST /v1/chat` classifies the latest user message, then uses explicitly saved Profile fields and the latest structured result for intentional context chaining. For triage only, one preceding user turn is carried forward when the latest text explicitly reads as a continuation, such as `cảm giác nó...`, `vẫn còn...` or a worsening update. Markers such as `yêu cầu mới`, `triệu chứng mới` and `chuyện khác` close that episode, preventing stale emergency symptoms from contaminating a new assessment. Explicit patient references in the latest message override stale session context. Every fresh response persists one user/assistant exchange; an idempotent replay does not duplicate history. Symptoms, medication safety, monitoring, follow-up and pharmacy can execute without a Profile by using a deterministic conversation-scoped technical reference that is not returned as a real patient identity. FHIR, OCR and medication schedules continue to require an explicit patient reference because they create or export patient-linked state. Missing clinical fields produce `needs_information` rather than fabricated values.

### Grounded answer contract

The user-facing answer is rendered after the domain service returns and cannot change its decision. The response path is `domain result -> GroundedAnswer facts -> deterministic narrative blocks -> React renderer`. `GroundedAnswer` contains a title, bounded summary, key points, next steps, safety notes, unanswered questions, decision basis, evidence state, rule version, source metadata, approval status, limitations and a human-review flag. Its `narrative` blocks contain plain text plus exact emphasis substrings; they cannot carry HTML or introduce claims outside those bounded fields. React renders the prose with text nodes and `<strong>` elements, never `dangerouslySetInnerHTML`.

Chat history persists the complete grounded object separately from the raw domain result so reopening a conversation preserves readable prose, its evidence lineage and the original machine-verifiable decision. Technical rule details remain available behind progressive disclosure rather than interrupting the conversational answer.

### Gateway-routed answer agents

The optional answer pipeline executes only after a deterministic domain result exists:

```text
latest user question
    -> redact patient reference, email and phone number
    -> immutable claims from the versioned domain result
    -> deterministic risk/cache policy and pre-call token guard
    -> HMAC-scoped identity, context, prompt, knowledge and tool-result versions
    -> LiteLLM /v1/responses with a budgeted MedGuard virtual key
    -> research alias routes to the question/evidence provider with web search
    -> accept only search queries and citation URLs from provider metadata
    -> reject sources outside the trusted authority-domain allowlist
    -> verifier alias routes independently with a fresh web search
    -> deterministic release gate checks citations, scores and locked claims
    -> verified narrative OR unchanged deterministic fallback
```

`MEDGUARD_AGENT_MODE` supports `disabled`, `shadow` and `enforced`. Shadow mode records evaluation traces but never replaces the deterministic answer. Enforced mode releases model-written prose only when both provider calls succeed and every deterministic gate passes. A timeout, malformed structured output, missing search evidence, untrusted source, verifier rejection, threshold failure, changed safety instruction or open circuit returns the original deterministic narrative.

The research role does not receive the stored Profile or raw domain object. It receives the redacted latest question, intent, an allowlist and bounded claims. The verifier receives those claims, the candidate draft, and the actual research search metadata. It must conduct its own web search, and at least one source returned in its provider metadata must belong to the trusted authority list. Model-authored source names, URLs or scores alone never satisfy the gate.

The application never stores provider credentials and has no supported direct-provider bypass. LiteLLM owns the fixed physical model mapping, usage/cost accounting, virtual-key budgets and distributed limits. Research and verification aliases cannot substitute for each other, so an answer-role failure cannot turn the verifier into the author. Every patient-specific request sends `store=false` plus LiteLLM `no-cache` and `no-store`; semantic caching is default-off because a semantically similar medical question may belong to a different patient or conversation.

Before the gateway call, the LLM control plane classifies the bounded chat intent, rejects estimated input beyond the configured context budget and assigns separate output caps to answer and verifier roles. Only versioned product-registry verification currently receives short-lived exact caching and single-flight coalescing. Cache material includes HMAC-pseudonymized tenant/conversation scope, locale, patient-context hash, prompt version, knowledge version and deterministic tool-result hash; it never uses raw identity in Redis keys or LiteLLM customer/session headers. Clinical, personalized and multi-turn medical traffic never enters that response cache.

LiteLLM uses bounded retry, cooldown and per-key concurrency for two fixed role aliases. Unsupported capabilities remain fail-closed because the application still requires search metadata, trusted citations and the independent verifier. The optional model layer therefore degrades to the precomputed deterministic answer rather than exposing an unverified draft.

The displayed grounding, safety, completeness and citation scores are verifier assessments plus deterministic contract checks. They reduce unsupported output but do not prove clinical truth or replace clinical validation. Physical model identifiers are pinned and reviewed in the gateway deployment, outside the public API contract. Application readiness requires an enforced, reachable gateway when agents are mandatory, but it does not claim the mapped models are clinically validated.

Provider identities, model identifiers, prompts, intermediate question analysis, search queries, verifier URLs, fallback reasons and orchestration state are confidential server-side data. They are excluded from `ChatResponse`, conversation history and the public OpenAPI schema. The client receives only `answer_assurance.status=verified`, bounded quality scores, the final answer and the final sources required for user inspection. Rejected, shadow and failed agent attempts are indistinguishable from the deterministic baseline in the user interface.

The client exposes only one in-flight message, `MedGuard đang xử lý`, with a minimum visible duration of 1000 ms so fast deterministic responses do not flash. The completed response is buffered and inserted only after this state ends. The chat surface omits the internal evidence disclosure and raw business-result panels; supported researched claims may still carry compact inline source links. It does not disclose which provider is enabled, which model is active, how many stages have completed or whether the deterministic fallback was used.

Clinical routing evaluates the latest user request plus explicitly saved Profile data. Explicit tool selection wins first, followed by specific intent phrases; short generic symptom markers then fall back to triage, medication-use language falls back to safety, and only a genuinely ambiguous request asks for clarification. It does not concatenate stale symptoms from earlier turns into a fresh triage decision. Numeric vitals recognized in the latest triage message are passed into `TriageRequest`; missing fields remain missing. A low medication-risk result is worded as "no warning found within the checked scope", never as proof that a medicine or combination is safe. A QR registry match is explicitly not presented as proof of physical authenticity.

This contract follows the transparency, human oversight and continuous-evaluation principles in [WHO guidance for AI in health](https://www.who.int/news/item/28-06-2021-who-issues-first-global-report-on-artificial-intelligence-ai-in-health-and-six-guiding-principles-for-its-design-and-use). It also keeps the recommendation basis independently inspectable, consistent with the [FDA Clinical Decision Support Software guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software). These references guide system design; they do not constitute clinical approval of the repository fixtures.

### Triage resolution

Triage evaluates emergency red-flag patterns from `red_flag_protocols.json` and supplied vital signs against knowledge-backed thresholds. A red flag produces `EMERGENCY` with specialty routing (CARDIOLOGY, NEUROLOGY, etc.); urgent but non-emergency vital abnormalities produce `URGENT`; otherwise the engine routes to the best-matching specialty from 13 configured specialties and returns `ROUTINE`. Versioned symptom guidance can add focused questions, bounded self-care and safety-net instructions after severity resolution; it cannot lower the resolved urgency. The current headache guidance cites NICE CG150 and NHS headache advice in its source metadata.

### Medication safety resolution

The safety engine performs five sequential checks:

1. **Unknown ingredients**: Missing/empty medication data → `requires_human_review=true`
2. **Allergy cross-reactivity**: 7 allergy groups from `allergy_cross_matrix.json` covering penicillin/beta-lactam, sulfonamide, NSAID, macrolide, fluoroquinolone, opioid, and local anesthetic families
3. **Drug-drug interactions**: 10 clinically significant pairs from `drug_interactions.json` including warfarin+aspirin, simvastatin+clarithromycin, fluoxetine+tramadol, lithium+NSAID
4. **Condition contraindications**: 6 medication groups from `contraindications.json` covering NSAIDs, ACE inhibitors, metformin, statins, beta-blockers, and isotretinoin
5. **Duplicate active ingredients**: Detects identical active ingredients across current and proposed medications

Warnings are marked with `basis=structured_table` and carry `severity`, `tier` (HARD_STOP/SOFT_STOP), `confidence`, and `recommendation` fields.

### Queue resolution

Queue items are sorted deterministically by emergency status, urgency, ESI, capped waiting time and input order. `priority_score` is an engineering ordering score, not a clinical severity score. A queue item with `emergency_flag=true` is returned with `priority_band=EMERGENCY` even if its incoming urgency field is inconsistent.

### Follow-up and monitoring resolution

Follow-up only creates dates when a configured rule matches. No-match returns `status=unknown`, `plan_available=false` and an empty suggestion list. Monitoring evaluates the latest value against safety thresholds immediately, even with one point, while trend analysis requires three points for the same metric. Trend interpretation is metric-aware: decreasing SpO2 is worsening, while decreasing pain or temperature is improving. Range-dependent metrics such as heart rate do not receive a health interpretation from direction alone.

## 6. Asynchronous OCR Flow

```text
Client uploads image
    -> validate content type, non-empty body and max size
    -> compute SHA-256 fingerprint
    -> persist job metadata and write image to the active TTL object store
    -> enqueue a tenant-scoped job message
    -> return HTTP 202 { job_id, poll_url, status: queued }
    -> worker atomically claims the exact job into a processing list
    -> worker retrieves the exact stored object
    -> real OCR pipeline must preprocess, detect, recognize, normalize and catalog-match
    -> low-confidence/unknown lines remain reviewable and never force-match
    -> pharmacist/doctor confirms the completed extraction
    -> explicit times, day periods or prescribed daily frequency become tenant-scoped reminders
    -> customer polls GET /v1/jobs/{job_id} or consumes a future callback adapter
```

The current worker intentionally fails a claimed job with `ocr_worker_unavailable` because no real OCR backend is configured. Missing objects fail with `ocr_source_object_missing`. Detector and recognizer adapters have no sample-text or synthetic-image fallback; test doubles exist only inside tests. Redis claims use `BLMOVE`; acknowledged messages are removed from `processing`, while abandoned claims are reclaimed and exhausted claims move to `dead-letter`.

QR verification is also fail-closed: unknown payloads remain `unknown`, malformed payloads are `invalid`, mismatched serial/lot values are `suspected_counterfeit`, and recalled registry records are `recalled`. `registry_match` means the decoded fields match the current development snapshot; it does not establish physical authenticity and production requires manufacturer/regulator data.

## 7. Cross-Cutting Safety Invariants

- Schema errors are returned as HTTP `400` with `error_code=invalid_payload`.
- Missing or invalid tenant credentials and idempotency headers are explicit errors.
- Reusing an idempotency key with a different normalized payload returns HTTP `409`.
- A first request atomically reserves its idempotency key; a concurrent duplicate receives `idempotency_in_progress` instead of executing the same side effect twice.
- Prescription processing claims use a database compare-and-set transition, so an API instance and OCR worker cannot both move the same job from `queued` to `processing`.
- Every response receives an `X-Request-Id` header; domain responses also expose `request_id`.
- Rate-limit responses expose the limit, remaining capacity, reset delay and `Retry-After`; health/readiness probes are exempt.
- Production rate limiting requires atomic Redis state and fails closed when that backend is unavailable.
- API responses use `Cache-Control: no-store`; the React shell receives a restrictive CSP and anti-framing/browser capability headers.
- Dynamic job paths are normalized to `/v1/jobs/{job_id}` labels before metrics are recorded.
- Protected domain operations append audit metadata with tenant, request, action and result summary.
- Medication-related outputs remain human-reviewable.
- OCR output cannot create a reminder until the job is completed and explicitly confirmed; missing scheduling instructions remain unresolved.
- The service does not claim diagnosis, prescription issuance or medication dispensing authority.
- Development rules and scores are labeled as fixtures and must not be presented as clinically validated.
- Knowledge files carry `_meta.approved_by` = `[PENDING]` until clinical validation.

## 8. Implementation Status And Production Gap

### Implemented development behavior

- Versioned FastAPI/OpenAPI boundary and Pydantic schemas.
- Tenant credentials, idempotency, request tracing and standardized errors.
- **Versioned structured knowledge base** with SHA-256 integrity verification:
  - 10 drug-drug interaction pairs with severity tiers
  - 7 allergy cross-reactivity groups with partial cross-reactivity
  - 7 emergency red-flag patterns with specialty routing
  - 4 vital sign threshold definitions
  - 13 specialty routing rules
  - 6 condition-based contraindication groups
- Knowledge-backed deterministic adapters for all nine documented capabilities.
- Specialty routing to 13 Vietnamese medical specialties (Cardiology, Neurology, GI, Pulmonology, etc.)
- Durable tenant-scoped OCR jobs and fail-closed worker with stale-claim recovery.
- Database-backed audit and idempotency repositories with restart tests.
- PostgreSQL pooled adapter, RLS schema/init script and Redis reliable queue adapter with atomic race-safe reclaim.
- Model registry response and circuit-breaker component.
- Runtime readiness endpoint that exposes active development fallbacks and production blockers.
- Regression suite covering API contracts, safety paths, tenant isolation, knowledge integrity, specialty routing, medication safety, monitoring semantics, OCR failure paths and infrastructure adapters.
- Repeatable development validation runner and a production benchmark gate that rejects missing OCR evidence.
- Same-origin React clinical workspace for all nine capabilities, with responsive browser smoke tests and explicit development readiness visibility.

### Required before production or clinical use

1. Deploy and exercise PostgreSQL/RLS with backup/restore and independent tenant-isolation tests.
2. Deploy Redis with persistence, worker supervision and dead-letter alerting.
3. Object storage with encryption, retention/TTL and consent policy if images are retained.
4. Versioned, clinically approved medication knowledge (replace `_meta.approved_by = [PENDING]` with actual clinical pharmacist sign-off), catalog matching and FHIR R4 adapter.
5. Real OCR pipeline with per-field confidence, bounding boxes and mandatory review workflow.
6. Model registry with checksum, license, prompt/version metadata and controlled rollout.
7. Distributed rate-limit deployment evidence, secret manager, webhook replay protection and key rotation.
8. OpenTelemetry metrics/traces, alerting, SLOs and operational dashboards.
9. BookingCare/HIS/EMR/consent integrations and clinical validation/legal review.
