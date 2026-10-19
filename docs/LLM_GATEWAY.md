# MedGuard LiteLLM Gateway

## Purpose

LiteLLM is the only LLM network boundary for MedGuard. The API process knows one virtual key and six logical role/domain aliases; provider keys, fixed physical model mappings, budgets and cost records stay in the gateway environment.

Non-test runtimes default to synchronous `enforced` Writer→Reviewer execution with coverage `all`. Clinical tools establish the safety floor, Writer composes from the active episode and structured evidence, and Reviewer plus the local release gates must pass before verified release. Missing configuration, capacity rejection, deadlines and quality failures return explicitly unverified safety fallback; emergency guidance remains available. Production readiness requires a proven live contract, approved clinical evidence and appropriate infrastructure. See [live release checks](live-agent-release-check.md).

An explicitly configured background/shadow profile is available for observation. `shadow_pending` means queued, not verified; its in-process queue does not survive restart. Background review is not a substitute for enforced pre-release verification.

The deployed stack is defined in `infrastructure/litellm/`:

- LiteLLM exposes OpenAI-compatible `/v1/responses` and `/v1/chat/completions` endpoints on port 4000. The Ollama profile uses chat completions with JSON Schema output.
- PostgreSQL persists virtual keys, spend and gateway metadata.
- Redis coordinates routing, rate limits and optional exact cache entries.
- Prometheus scrapes gateway metrics on port 9090.

## Model Roles

`medguard-answer` maps only to the question-analysis and evidence-search model. `medguard-verifier` maps only to the quality-verification role that searches again and grades grounding, safety, completeness and citation coverage. The two aliases cannot substitute for each other. The frontend and public chat schema never expose these mappings, prompts, intermediate output or provider failures.

All gateway profiles preserve the same six logical role aliases:

- `config.ollama.yaml`: Qwen 2.5 3B for both stages. It has no provider-token charge, but the two stages are not independent.
- `config.gemini-free.yaml`: Gemini 2.5 Flash with quota-limited free Google Search grounding and local MedGemma 1.5 4B verification. This avoids OpenAI charges and separates model families, but remains a deidentified development/staging profile rather than clinician judgment. The 3.3 GB Q4 MedGemma build is the practical medical reviewer for this 8 GB development machine; larger 27B-class models do not fit reliably.
- `config.yaml`: Gemini 3.8 Flash analysis and OpenAI GPT-5.6 Sol verification. This is the requested independent cloud judge profile; OpenAI API usage is paid.

The deterministic release gate remains authoritative in every profile. Before claiming independent clinical verification, document privacy and retention controls and rerun a blinded clinician-reviewed evaluation.

## Coverage and Request Policy

`MEDGUARD_AGENT_COVERAGE_SCOPE=clinical` reviews triage and medication-safety responses. `all` submits every public response type, regardless of whether its outcome is `answered`, `needs_information`, or `unsupported`. Prompt-injection, toxic-content and self-harm text is replaced with a deterministic guard verdict before model review. Background processing is observability-only by default. When `MEDGUARD_AGENT_BACKGROUND_PROMOTE_VERIFIED=true`, it may progressively update durable history only after the full release contract passes; strict first-render pre-release processing still requires `enforced + synchronous` and must report explicit failure status.

`app/services/llm_control_plane.py` is the application-side policy point before every agent call. The classification is deliberately based on a bounded intent enum rather than model-authored risk labels.

| Request class | Current intents | Cache | Verifier | Coalescing |
|---|---|---|---|---|
| `clinical_high_risk` | triage, medication safety, monitoring | `no-cache`, `no-store` | required | off |
| `personalized` | follow-up, pharmacy | `no-cache`, `no-store` | required | off |
| `safe_dynamic` | versioned product-registry verification | exact, short TTL | required | on |
| `safe_static` | reserved for a future isolated public FAQ route | exact, short TTL | optional by policy, not currently released through the agent pipeline | on |

Current model-assisted medical flows always require the independent verifier. There is no production route that skips verification for clinical advice.

## Cache Isolation

MedGuard does not enable semantic cache for patient-specific, multi-turn or agentic traffic. Similar wording does not imply the same patient, history, dose, allergy, urgency or current evidence, so a semantic hit could replay an unsafe answer across contexts. This follows LiteLLM's own warning for multi-turn and agentic cache workloads.

Clinical and personalized calls always include:

```json
{
  "store": false,
  "cache": {"no-cache": true, "no-store": true}
}
```

Gateway cache mode is `default_off`; exact cache must be opted into by policy. Its scope is derived from HMAC-pseudonymized tenant/conversation identity, role, locale, patient-context hash, prompt version, knowledge version and deterministic tool-result hash. Raw tenant IDs, patient references and questions are never used as Redis keys or LiteLLM customer/session headers.

For exact-cache-safe calls, an in-process single-flight returns the same result to concurrent callers. When the application Redis backend is available, a short distributed lock prevents parallel replicas from producing the same miss; waiting replicas then use LiteLLM's exact cache. No clinical response body is stored in application Redis.

Stable system instructions are sent before changing input, and a pseudonymous session header preserves deployment affinity. Provider prompt caching remains provider-controlled; MedGuard records cached-input token usage when the gateway returns it and does not pretend a prompt-cache hit occurred.

## Token And Budget Control

The control plane estimates input size conservatively before network I/O and fails back to the deterministic answer when `MEDGUARD_AGENT_MAX_INPUT_TOKENS` is exceeded. Separate answer/verifier output caps prevent unbounded generation. The gateway virtual key adds independent RPM, TPM, monthly budget, expiry and maximum-parallel-request limits; provider accounts remain the final quota layer.

The application never truncates locked clinical claims to fit a model context. An oversized request is rejected at the optional presentation layer while the deterministic domain result remains available.

## Routing And Failure Policy

The application calls only the two logical aliases. LiteLLM applies bounded retries, failure cooldown, budget limits and per-key concurrency without changing role ownership. Final release requires valid structured output, provider search metadata, trusted sources, immutable clinical instructions and verifier thresholds. Exhausted retries or either unavailable role return the precomputed deterministic answer.

Safe degraded mode is therefore the already computed deterministic response, not an unverified model draft. Gateway timeout, budget exhaustion, malformed output, missing citations, open circuit and verifier rejection all converge on that same behavior.

## Local Deployment

```bash
cd infrastructure/litellm
cp .env.example .env
# Select config.ollama.yaml for local inference; cloud provider keys are optional in that profile.
docker compose up -d
docker compose ps
```

## Gemini analyzer and independent judge

There is no proprietary ChatGPT or Gemini model bundled inside Ollama. Ollama's OpenAI compatibility means API-shape compatibility, not access to OpenAI's hosted ChatGPT models.

For a quota-limited, zero-provider-charge development profile, put a Gemini Developer API free-tier key in the untracked `infrastructure/litellm/.env` and select:

```dotenv
LITELLM_CONFIG_FILE=./config.gemini-free.yaml
GEMINI_API_KEY=<gemini-key-from-google-ai-studio>
OPENAI_API_KEY=
```

This routes `medguard-*-answer` to Gemini 2.5 Flash and `medguard-*-verifier` to local `medgemma1.5:4b`. Gemini 2.5 Flash is used here instead of Gemini 3.x because Google's current free API tier includes a limited Google Search grounding quota for 2.5 Flash, while Search grounding for Gemini 3.x is not available on the API free tier. It is intentionally restricted to development/staging metadata. Google states that free-tier Gemini inputs may be used to improve its products; therefore this profile is only for deidentified test data. The local judge is useful as a second model-family signal, but it is not equivalent to a clinician judgment and cannot guarantee zero hallucinations.

Install the local reviewer once:

```bash
ollama pull medgemma1.5:4b
```

For the requested Gemini analyzer plus an actual OpenAI judge, select:

```dotenv
LITELLM_CONFIG_FILE=./config.yaml
GEMINI_API_KEY=<gemini-key>
OPENAI_API_KEY=<openai-platform-key>
```

The cloud profile routes every answer/analyzer alias to `gemini-3.8-flash` and every verifier/judge alias to `gpt-5.6-sol`. It is not free: a ChatGPT subscription does not supply API usage, and OpenAI bills API tokens separately. Use a low-budget LiteLLM virtual key, provider budget alerts and deidentified shadow traffic before considering production.

Keep the application on the low-latency non-blocking path while evaluating either mixed profile:

```dotenv
MEDGUARD_AGENT_MODE=shadow
MEDGUARD_AGENT_SYNC_ENABLED=false
MEDGUARD_AGENT_BACKGROUND_ENABLED=true
MEDGUARD_AGENT_BACKGROUND_PROMOTE_VERIFIED=true
MEDGUARD_LLM_GATEWAY_API_STYLE=chat_completions
MEDGUARD_AGENT_WEB_SEARCH_ENABLED=true
MEDGUARD_AGENT_WEB_SEARCH_REQUIRED=true
MEDGUARD_VERIFIER_WEB_SEARCH_ENABLED=false
MEDGUARD_VERIFIER_WEB_SEARCH_REQUIRED=false
```

The patient receives the deterministic answer immediately. Gemini combines the bounded internal retrieval context with Google Search. The adapter uses two gateway calls because Gemini 2.5 Search tool output and forced structured JSON are not safely combined in one request: pass 1 returns provider-grounded research metadata; pass 2 converts that evidence to the strict MedGuard schema without another search. MedGuard then fetches at most two model-selected HTTPS pages from the medical domain allow-list and supplies their stripped text to the local MedGemma reviewer. Only a result that passes schema, search-metadata, reachable-source, claim-linkage, score and deterministic safety gates is promoted in durable history; the UI polling path replaces the displayed answer and labels it `gateway_verified`. Any failure preserves the deterministic answer.

The runtime fetcher is not an unrestricted crawler and does not auto-train the system. It rejects non-HTTPS/unapproved domains, cross-domain redirects, unsupported content types and oversized responses. Runtime text is ephemeral. Persistent additions still go through `scripts/crawl_medical_sources.py`, `scripts/refine_crawled_dataset.py` and human approval before entering `crawled_clinical_guidelines.json`.

Generate a dedicated backend key with allowed aliases, a 30-day budget window, RPM/TPM limits and a 90-day expiry:

```bash
cd ../..
LITELLM_MASTER_KEY='<master-key>' \
  .venv/bin/python scripts/bootstrap_litellm_key.py \
  --team-id medguard-backend --max-budget 100 --rpm-limit 120 \
  --max-parallel-requests 1
```

Store the returned value in the deployment secret manager as `MEDGUARD_LLM_GATEWAY_API_KEY`. Do not copy the LiteLLM master key or provider keys into MedGuard.

Validate liveness and both production aliases without patient data:

```bash
MEDGUARD_LLM_GATEWAY_URL=http://127.0.0.1:4000/v1 \
MEDGUARD_LLM_GATEWAY_API_KEY='<virtual-key>' \
  .venv/bin/python scripts/check_llm_gateway.py --probe-models
```

## Promotion Gates

1. Run `shadow` on a deidentified, clinician-reviewed set. The deterministic answer remains visible.
2. Measure schema success, search execution, citation reachability, claim support, verifier rejection, severe safety misses, p95 latency and cost per accepted answer.
3. Review provider retention/training controls, regional processing, DPA/legal basis and incident response before sending any clinical text.
4. Pin gateway image/model versions; exercise each role failure, 429 budgets, Redis loss and provider timeout.
5. Promote to `enforced` only when clinical, privacy, security and operations owners approve the evidence.

The application fails back to its deterministic narrative when a model times out, returns malformed output, lacks provider-native search evidence, cites an untrusted domain, changes a locked clinical claim or fails verifier thresholds. This reduces hallucination risk; it does not prove that the final answer is medically correct.

## Operations

- Liveness: `GET /health/liveliness` on LiteLLM.
- Model/provider health: run `scripts/check_llm_gateway.py --probe-models` from a controlled environment.
- Metrics: Prometheus at `http://127.0.0.1:9090`; configure authenticated remote dashboards before production.
- Rotation: generate a replacement virtual key, deploy it, verify readiness, then revoke the old key.
- Cost control: enforce per-key budget, RPM and TPM limits and alert before budget exhaustion.
- Privacy: never log prompts/responses, disable provider storage where supported and keep gateway/database access restricted.
- Application metrics: monitor `medguard_llm_pipeline_total`, stage requests/latency, input/output/cached tokens, policy blocks, quality rejections, no-store calls and single-flight outcomes. Labels are bounded to role, risk, cache and status; they never contain patient or tenant identity.

Do not infer gateway activation from polished prose. Public chat responses carry `answer_origin`, `verification_status` and `knowledge_approval`. Readiness reports transport (`llm_gateway_transport`), completed writer/verifier contract evidence (`llm_model_contract`) and execution policy (`answer_agents`) separately; gateway liveness alone is not proof that either model satisfies the structured contract. Background outcomes are counted in `medguard_llm_background_total`.

If a future non-blocking public enhancement path is enabled after approval, verify its complete release contract with deidentified input:

```bash
.venv/bin/python scripts/check_verified_answer_flow.py
```

The command exits nonzero on the current deterministic-only synchronous release because no model-authored source is exposed. It is an opt-in enhancement-contract probe, not a health check for the low-latency chat path.
