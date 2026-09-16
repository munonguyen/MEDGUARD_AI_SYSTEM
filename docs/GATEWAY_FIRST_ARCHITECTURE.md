# Gateway-first architecture without mandatory RAG

## Decision

MedGuard must not depend on a retrieval hit in order to produce a response. Retrieval is a conditional evidence tool, not the router, the model, or the safety authority.

Every valid request must terminate in exactly one bounded outcome:

1. `answer` — enough governed evidence exists for a useful response;
2. `clarify` — required patient or task context is missing;
3. `abstain` — the system cannot support a medical claim safely;
4. `escalate` — an emergency, high-risk medication event, crisis, or human review is required.

“Answer every question” therefore means 100% protocol coverage, not 100% factual certainty. A medical assistant that invents an answer when evidence is absent is not more capable; it is less safe.

## Terminology

RAG is runtime retrieval-augmented generation. It is normally not a separately “trained RAG model”. Fine-tuning changes model parameters; retrieval supplies current or governed evidence at request time. MedGuard may answer a low-risk static request from bounded model knowledge, but patient-specific clinical claims, current guidelines, medication interactions, product recalls and local workflows still require a governed tool or evidence source.

The target is therefore **RAG-optional**, not **evidence-optional**.

## Open-source reference architectures

| Project | Useful pattern | MedGuard adoption | What it does not solve |
|---|---|---|---|
| [LangGraph](https://github.com/langchain-ai/langgraph) | Explicit state graph, durable execution, checkpointing and human-in-the-loop | Typed outcomes, explicit gates and resumable human review are the target orchestration contract | A graph framework does not make medical claims correct |
| [Haystack](https://github.com/deepset-ai/haystack) | Modular sync/async pipelines, routers, optional retrievers, generators and streaming | Retrieval becomes one conditional node; independent branches may run concurrently | Installing Haystack alone does not improve the local model or evidence quality |
| [LiteLLM](https://github.com/BerriAI/litellm) | One OpenAI-compatible gateway, virtual keys, budgets, guardrails, routing and load balancing | It remains MedGuard's only model network boundary and owns physical model selection | Gateway liveness is not proof that a writer/verifier contract completed |
| [vLLM](https://github.com/vllm-project/vllm) | Continuous batching, chunked prefill, prefix caching, streaming and structured outputs | Recommended production inference server when GPU deployment is available | Ollama on a development laptop cannot be assumed to match this throughput |
| [Dify](https://github.com/langgenius/dify) | Workflow orchestration with tools, model providers, RAG and operations separated | Confirms that retrieval should be an optional workflow capability | A general workflow UI is not a clinical safety case |
| [Open WebUI](https://github.com/open-webui/open-webui) | OpenAI-compatible/Ollama integration, tools, filters, multi-model and observability | Useful reference for provider neutrality and local development | It is a UI/platform, not a medical release gate |

MedGuard should keep its small typed domain services instead of importing a large agent framework immediately. The architectural patterns above can be implemented behind the existing API, then a graph runtime can be adopted only if durable pause/resume or complex tool fan-out becomes necessary.

## Target request flow

```text
request
  -> authentication / consent / rate limit / input bounds
  -> deterministic crisis, prompt-injection and medical red-flag guard
  -> typed gateway coverage policy
  -> intent + risk router
  -> conditional tool plan
       -> versioned medical rules or registry
       -> optional fresh retrieval/search
       -> operational tools (schedule, FHIR, pharmacy, OCR)
       -> no retrieval when it adds no value
  -> structured writer through LiteLLM
  -> independent verifier + deterministic invariant checks
  -> answer | clarify | abstain | escalate
  -> audit, metrics and deidentified evaluation capture
```

The pre-gateway emergency guard is intentionally retained. If the gateway is unavailable, a chest-pain or self-harm response must not wait silently for a model timeout. In `enforced` mode the gateway is attempted before routine response release; the public `verification_status` records whether it verified, timed out, rejected, failed, or was not requested. Emergency action remains deterministic and immediate, and may be reviewed asynchronously.

## Gateway coverage contract implemented in this repository

`MEDGUARD_AGENT_COVERAGE_SCOPE` now has two values:

- `clinical`: submit triage and medication-safety responses only;
- `all`: submit every public response type, including `needs_information`, unsupported-domain redirects and deterministic crisis responses.

Guarded harmful input is not forwarded verbatim. The gateway receives a deterministic verdict label and the already-generated safe response. This prevents an injection string from being reintroduced into the model assessment stage.

Coverage is observable through:

- public `verification_status` and `answer_origin`;
- `medguard_gateway_response_coverage_total{intent,status,scope,outcome}`;
- readiness check `gateway_response_coverage`;
- background completion audit event `chat.agent_shadow`;
- history updates from `shadow_pending` to `shadow` or `error`.

The coverage metric distinguishes `accepted`, `completed`, `attempt_failed`, and `not_requested`. The denominator must be all successful `/v1/chat` responses. Production alerts should fire when `not_requested > 0` under `scope=all`, or when accepted work ages without completion.

## Delivery policies and guarantees

| Configuration | Patient latency | What is guaranteed | Limitation |
|---|---:|---|---|
| `disabled` | Lowest | Deterministic safety path only | No model gateway coverage |
| `shadow + all + background` | Lowest | Every admitted response is queued for the local reviewer and reports pending/completed/failure | In-process queue is not crash-durable; backlog can grow if arrival rate exceeds Ollama throughput |
| `enforced + all + synchronous` | Bounded by request timeout | Every response attempts writer/verifier before release; result status is explicit | Provider failure still returns deterministic safe fallback unless fail-closed is added |
| Durable asynchronous outbox | Low | Accepted jobs survive API process restarts and can be retried/dead-lettered | Review completes after the patient response |

Strict “no delivered response unless gateway verification succeeded” is a fail-closed policy. It reduces availability and is unsafe for emergency instructions unless the emergency deterministic guard is exempt. This repository currently favors medical fail-safe behavior: model failure never suppresses an urgent deterministic action and never releases an unverified model draft.

For production, replace the in-process shadow executor with a dedicated Redis Streams/PostgreSQL outbox queue, an idempotent worker, visibility timeout, retry budget and dead-letter review. Do not mix model-review jobs with the OCR queue. Until that exists, background mode is an evaluation mechanism, not a delivery guarantee.

## Latency design

The useful service-level objectives are separate:

- emergency deterministic action p95 under 300 ms;
- gateway time to first token p95 under 2 s;
- short routine answer p95 under 10 s;
- background verification queue age and completion reported separately.

Two serial generations on the current local Qwen/Ollama profile cannot honestly be guaranteed under 10 seconds on every request. The production path should use streaming and a GPU-backed server such as vLLM, keep system prefixes stable, cap input/output tokens, warm models, use continuous batching, and run independent tool calls concurrently. Use one small router model only when deterministic routing confidence is low; do not spend a model call on obvious intents.

The UI timeout is not a performance optimization. It only stops waiting. Performance must be demonstrated using p50/p95/p99 time-to-first-token and full-response latency under realistic concurrency.

## Quality and medical release gates

The writer/verifier architecture is necessary but insufficient. Production promotion requires:

- clinician-reviewed hidden evaluation cases separated from development prompts;
- zero critical under-triage on the release-critical set;
- medication contraindication, allergy, overdose and duplicate-ingredient tests;
- calibrated abstention and no false reassurance;
- source entailment, freshness, approval state and citation reachability;
- Vietnamese clarity, empathy and actionability—not generic positive sentiment;
- adversarial prompt-injection, privacy and cross-tenant isolation tests;
- gateway outage, timeout, malformed-schema, queue backlog and retry tests;
- direct blinded comparison against the selected ChatGPT/Gemini model under the same context, tools, token budget and rubric.

The implemented natural-language quality evaluator classifies communication as `supportive_safe`, `alarming_but_appropriate`, `neutral`, `falsely_reassuring`, or `panic_inducing`, alongside explicit consistency, priority, uncertainty and professional-tone checks. “Positive” tone alone must never be optimized: a calm emergency escalation can be negative in sentiment and still be the medically correct response.

## Current assessment

The repository now has a credible safety-first baseline: deterministic red flags, bounded medical outputs, typed writer/verifier contracts, provider-neutral LiteLLM integration, model failure fallback, audit records, response provenance, deidentified evaluation capture and broad regression tests.

It is **not yet proven superior to ChatGPT or Gemini**, and it is **not yet production-ready for a 100% durable background-gateway guarantee**. The remaining high-priority work is:

1. durable model-review outbox and worker;
2. streaming endpoint and UI with measured TTFT;
3. production GPU inference benchmark (vLLM or equivalent);
4. independent verifier model family;
5. clinician-reviewed blinded benchmark and safety-case sign-off;
6. live evidence connectors with approval/freshness policies for claims that require current information.
