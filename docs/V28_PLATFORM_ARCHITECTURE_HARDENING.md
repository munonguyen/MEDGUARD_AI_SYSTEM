# MedGuard V28 — Platform Architecture Hardening

This note records the architecture decisions made after reviewing a reference AI platform built around Nginx, microservices, Kafka, PostgreSQL, Redis, vector search, object storage and observability. The reference is useful as a pattern library, but MedGuard must optimize for clinical safety and controlled failure, not service count.

## 1. Safety-critical path

The patient-facing clinical path remains synchronous and dependency-minimal:

```text
Client
  -> optional Nginx ingress
  -> FastAPI request/auth/consent/rate-limit
  -> deterministic clinical parsing + safety floor
  -> bounded Writer/Reviewer contract when enabled
  -> deterministic response-quality/safety release gate
  -> response
```

A failure of Redis, object storage, the background queue, metrics, RAG support services or external tracing must never be required to classify an active emergency. Production readiness can still fail closed when required infrastructure is unhealthy, but an already-running clinical process must not route emergency detection through an asynchronous event bus.

## 2. Reference components: adopt, adapt, or defer

| Reference component | MedGuard decision | Reason |
|---|---|---|
| Nginx | **Adopt as optional ingress** | TLS/reverse proxy/load-balancing boundary, request correlation and private metrics boundary. No clinical logic. |
| PostgreSQL | **Already implemented; keep** | Durable tenant-scoped source of truth, RLS, audit/job/history persistence. |
| Redis | **Already implemented; keep** | Shared rate limits, reliable job queue, coordination/cache. Never the clinical source of truth. |
| MinIO / S3 | **Already supported; keep** | Tenant-scoped prescription/document objects with production fail-closed behavior. |
| Worker services | **Already implemented; keep and separate** | OCR/background verification and other slow work stay off the synchronous response path. |
| Prometheus / Grafana | **Prometheus-compatible metrics already implemented; harden** | Useful for latency, failures and quality-gate telemetry. Raw tenant IDs and patient text are forbidden labels. |
| Langfuse | **Defer / optional adapter only** | Tracing is useful but raw prompts can contain PHI. A future adapter must default to redacted metadata-only traces. |
| Kafka | **Defer** | Existing Redis reliable queue already provides pending/processing/retry/dead-letter semantics. Kafka adds operational complexity without current evidence of required throughput or fan-out. |
| Qdrant | **Defer behind retriever abstraction** | Current curated knowledge snapshots and retriever are small, integrity-checked and deterministic. Introduce a vector DB only when corpus scale/semantic recall benchmarks prove a benefit. |
| Separate embedding microservice | **Defer** | No need to add a network hop until external document/RAG scale warrants it. |
| WebSocket/SSE | **UX-only if added** | Streaming may improve responsiveness but must never change triage or release-gate semantics. |

## 3. Observability hardening implemented in V28

`app/core/observability.py` now follows production-safe constraints:

- HTTP metrics automatically collapse `tenant_id` into bounded `tenant_scope` values (`configured`, `anonymous`, `untrusted`) to prevent tenant-name leakage and high-cardinality Prometheus series.
- Timing observations store only aggregate count/sum instead of an unbounded list of every request latency.
- Prometheus timing samples use valid `metric_count{...}` and `metric_sum{...}` naming.
- Metric and label names are validated; label values are escaped.
- Operational logs redact phone numbers, 12-digit citizen IDs and email addresses.
- Raw tenant IDs are not serialized by the MedGuard structured formatter.
- `X-Request-Id` remains the correlation key between ingress, API and governed audit evidence.

The monitoring stack is a **support plane**, not a clinical authority.

## 4. Ingress hardening implemented in V28

`infrastructure/nginx/medguard.conf` provides a reference reverse-proxy boundary:

- upstream keep-alive;
- bounded connection/read/send timeouts;
- request-size cap;
- forwarding of request correlation and standard proxy metadata;
- `/metrics` blocked from the patient-facing ingress.

TLS termination and certificates remain deployment-specific and are intentionally not fabricated in repository configuration.

## 5. When Kafka becomes justified

Do not introduce Kafka merely to match a diagram. Reconsider it when at least one measurable requirement exists, for example:

- multiple independent consumers need the same event stream;
- durable replay is operationally required;
- sustained background throughput exceeds the Redis queue target;
- event ordering/partitioning is required across services;
- a PostgreSQL outbox + queue design can no longer meet delivery SLOs.

If introduced, events should contain references and bounded metadata, not raw clinical narratives by default. Suitable event families include `document.ingested`, `evaluation.completed`, `notification.requested` and `quality_gate.rejected`. Emergency triage is excluded from this event path.

## 6. When a vector database becomes justified

Qdrant/another vector DB should be benchmark-driven. Introduce it behind the existing retrieval boundary only when:

1. the knowledge corpus grows beyond the efficient deterministic local index;
2. a sealed retrieval benchmark shows materially better recall/MRR/groundedness;
3. tenant/document isolation and deletion are proven;
4. retrieval failure has a safe deterministic fallback;
5. citations/provenance remain mandatory through the Writer/Reviewer release gate.

Vector similarity is evidence retrieval, never a triage decision rule.

## 7. Q&A quality evaluation

The 40-case medical response benchmark runs through the public `/v1/chat` API rather than testing the context router alone. It generates:

- `datasets/DS-MEDICAL-RESPONSE-QUALITY/eval_report.json`
- `artifacts/v28_response_quality/report.json`
- `artifacts/v28_response_quality/REPORT_40_QUESTIONS_ANSWERS.md`

Every report entry contains the real system answer, expected behavioral contract, actual urgency/intent, dimensional scores and reviewer notes. Labels are evaluation targets and remain non-production ground truth until independent clinical review is completed.

## 8. Production status is unchanged by architecture diagrams

Adding Nginx configuration or support-plane adapters does not make MedGuard production-authorized. The release-evidence manifest remains authoritative. Database/object-storage/queue credentials, consent enforcement, independent clinical validation, approved clinical knowledge and other external evidence must be real and reviewed; they must never be marked PASS simply because a Docker service can start.

## 9. Exposure scope and telemetry follow-up (2026-10-02)

The context router is now the sole source of chemical-exposure triggers for the respiratory domain. Long negated lists retain clause scope rather than losing negation after 40 characters; current versus hypothetical and latest-mention semantics remain in force. A closed room alone no longer constitutes chemical exposure. Commas introducing an explicit new subject or temporal assertion terminate stale negation, while commas inside an exposure list preserve it.

The telemetry registry bounds explicitly supplied `tenant_scope` values as well as legacy `tenant_id` labels. When both are supplied, the scope derived from the tenant identifier takes precedence, preventing duplicate Prometheus labels. Structured logs apply the same scope bounds. Rate-limit rejections now honor `metrics_enabled` while retaining rejection status, correlation and security headers.

Public API regression coverage verifies that negated chemical exposure is not fabricated as an inhalation incident. **Known independent limitation:** the legacy `severe_respiratory_distress` rule still matches generic `khó thở`, including mild wording. The context-router fix does not downgrade that independent safety rule or establish calibrated public-API dyspnea triage. That rule requires a separate change with explicit emergency-preservation regressions.

Two older regression assertions were updated to verify the current dose-reasoning and exercise-soreness contracts rather than obsolete exact prose. The paracetamol case still requires human review, an urgent assessment, a calculated total of 2000 mg, no further paracetamol and no induced vomiting. The exercise-soreness case still requires non-pharmacological care and worsening-symptom follow-up.

Verification on this change: `.venv/bin/python -m pytest -q app/tests` passed **755 tests**. The public API benchmark (`scripts/evaluate_medical_response_quality.py --no-report`) passed **40 cases**, with **0 critical failures**, **0 subthreshold cases**, a **13.07/14** average and **679 ms** p95 in the local deterministic test environment. These are regression/evaluation results, not independent clinical validation or production-LLM performance evidence. No UI files changed and no new browser verification was performed for this patch.

## 10. Full-output audit supersedes a high rubric score (2026-10-02)

The question-and-answer review requested before pushing code is implemented in `scripts/audit_v28_output_quality.py`. It captures 60 fresh `/v1/chat` responses (40 original cases and 20 context challenges), preserves raw JSON and narrative, and projects the default displayed fields using the limits/order in `GroundedAnswer.jsx`. It does not substitute reference answers, assume perfect grounding, or invent runtime tool trajectories.

The recorded audit runs in development with `agent_mode=enforced`, synchronous agent coverage `all`, and no configured external gateway. Side effects disabled are background-agent submission and active-learning capture. This exposes the real deterministic degradation path; it is not a live Gemini assessment.

Results: projected-text rubric average **13.13/14**, but only **20/60** satisfy all strict checks; **40/60** need review. There are **8 urgency disagreements**, **6 intent-check failures**, **12 required-content failures**, and **2 forbidden-content hits**; these counts overlap. Default-view professional gate passes **37/60**, narrative gate **60/60**, and the post-hoc heuristic jury **2/60**. The jury is not an independent LLM/clinical panel, and its low pass rate does not establish that 58 answers are medically incorrect. Some heading/order flags also require browser and evaluator review. The strict audit deliberately exits with code **1 / FAIL**.

Confirmed review findings include missing warfarin–ibuprofen interaction content in the gateway-unavailable fallback and unsupported acute-respiratory-failure wording in mild-dyspnea responses. Other urgency labels, including pregnancy scenarios, remain provisional pending clinical review. Ada/Buoy documentation was compared as a capability reference; no paired competitor answer benchmark was run, so superiority is **not proven**.

Generated evidence is under `artifacts/v28_output_audit/`; the HTML contains all answers, score reasons, manual review notes, raw responses and downloadable JSON. Four audit-integrity unit tests plus two existing benchmark tests passed. The push recommendation is **false**; no push follows this audit while these output defects remain unresolved.


## 11. Fixes from the full-output audit (2026-10-02)

The unavailable-gateway path now preserves explicit medication-safety questions, including warfarin–ibuprofen. Ordinary headache no longer fabricates a head-trauma syndrome; real head injury and new severe headache on anticoagulants retain emergency handling. The respiratory protocol no longer asserts acute respiratory failure or suggests an unprescribed bronchodilator. Explicit mild dyspnea is assessed urgently while severe respiratory findings, chest red flags, toxic exposure and abnormal vital signs retain their independent emergency paths.

Semantic matching no longer confuses Vietnamese `toàn thân` with renal disease or treats negated urinary retention as present. The legacy toxicology signature router respects negated exposure lists. Exertional chest-pressure explanations now describe the exertional evidence rather than inventing autonomic symptoms. No chest-pain or obstetric warning was downgraded to satisfy provisional benchmark labels.

Emergency titles and opening summaries state the action first; internal ESI/routing prose is removed from the patient answer while structured clinical metadata remains available. Lab answers expose interpretation points, follow-up questions and next actions. Explicit nutrition, missed-dose, medication-sharing, misinformation and diagnostic-limitation questions receive bounded education when no current safety-floor concern or ongoing multi-turn episode is present. Non-emergency triage calls the contextual answer planner even when no symptom template matches, restoring antibiotic and hydration explanations.

The new API regression suite forces enforced synchronous agents with all-intent coverage and explicitly unavailable providers. It includes positive emergency controls and negative/hypothetical controls; responses are never replaced by reference answers. The original 40-case benchmark remains separate from the stricter 60-case audit.

Final counts and validation evidence are recorded in `artifacts/v28_output_audit/MedGuard_V28_Output_Audit.json`. The HTML retains the original answers, downloadable raw JSON, evaluator reasons, baseline comparison and updated review status. Three urgency targets remain unapproved: pregnancy with pain/bleeding, chest pain after push-ups without examination or reproducibility details, and exertional chest pressure. Keep the output gate FAIL and do not push until these targets and remaining independent validation requirements are resolved.

Frontend compilation succeeds. Browser verification was attempted but the Chromium download returned an invalid archive; desktop/mobile DOM and visual checks remain NOT RUN. The heuristic jury and professional gate are internal software checks, not independent clinical assessment or evidence of superiority over Ada/Buoy.

Validation for source commit `effe815`: **783 tests passed** in the complete pytest suite; **28 targeted audit/regression tests passed**. Frontend `npm run build` passed. The separate 40-case benchmark passed with **13.68/14**, **0 critical failures**, and **0 subthreshold cases**. The 60-case strict audit improved from **20/60 to 57/60**, with **13.75/14** projected-text average, professional default and narrative gates both **60/60**, and the post-hoc heuristic jury **6/60**. All remaining strict flags are the three urgency disagreements above. Its exit code **1** is the intended FAIL gate, not a successful promotion. No push was attempted.
