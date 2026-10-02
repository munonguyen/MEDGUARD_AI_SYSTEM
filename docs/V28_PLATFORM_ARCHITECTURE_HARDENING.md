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
