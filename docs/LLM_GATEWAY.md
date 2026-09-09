# MedGuard LiteLLM Gateway

## Purpose

LiteLLM is the only LLM network boundary for MedGuard. The API process knows one virtual key and two logical aliases; provider keys, fixed physical model mappings, budgets and cost records stay in the gateway environment.

```text
React UI -> FastAPI -> deterministic clinical decision
                      -> redact and bound approved claims
                      -> risk/cache/token policy
                      -> pre-call input guard + exact-safe single-flight
                      -> LiteLLM virtual-key authentication
                         -> RPM/TPM/budget checks
                         -> fixed role alias routing and bounded retries
                         -> centralized usage/latency/cost metrics
                      -> independent deterministic release gate
                      -> final answer or deterministic fallback
```

The deployed stack is defined in `infrastructure/litellm/`:

- LiteLLM exposes the OpenAI-compatible `/v1/responses` endpoint on port 4000.
- PostgreSQL persists virtual keys, spend and gateway metadata.
- Redis coordinates routing, rate limits and optional exact cache entries.
- Prometheus scrapes gateway metrics on port 9090.

## Model Roles

`medguard-answer` maps only to the question-analysis and evidence-search model. `medguard-verifier` maps only to the independent quality model that searches again and grades grounding, safety, completeness and citation coverage. The two aliases cannot substitute for each other. The frontend and public chat schema never expose these mappings, prompts, intermediate output or provider failures.

The current deployment template uses exactly `gemini-3.1-pro-preview` for research and `gpt-5.6-sol` for independent verification. There is deliberately no cross-role or weaker-model fallback: if either role is unavailable, the agent draft is not released and the deterministic answer remains visible. These are operational defaults, not a clinical endorsement. Change physical model IDs only in `infrastructure/litellm/config.yaml`; keep the application aliases stable and rerun shadow evaluation before promotion.

## Request Policy

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
# Set long random secrets plus restricted GEMINI_API_KEY and OPENAI_API_KEY.
docker compose up -d
docker compose ps
```

Generate a dedicated backend key with allowed aliases, a 30-day budget window, RPM/TPM limits and a 90-day expiry:

```bash
cd ../..
LITELLM_MASTER_KEY='<master-key>' \
  .venv/bin/python scripts/bootstrap_litellm_key.py \
  --team-id medguard-backend --max-budget 100 --rpm-limit 120 \
  --max-parallel-requests 20
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

Do not infer agent activation from polished prose in the browser. `GET /v1/health/readiness` must report the provider-neutral `answer_agents` check as healthy, and an accepted request must increment `medguard_llm_pipeline_total{status="verified"}`. A released answer also carries public `answer_assurance.status=verified`; model names, prompts, intermediate analysis and rejection reasons remain excluded.

After the alias probe passes and the MedGuard API is restarted with `MEDGUARD_AGENT_MODE=enforced`, verify the complete public release path with deidentified input:

```bash
.venv/bin/python scripts/check_verified_answer_flow.py
```

The command exits nonzero unless both independent verification and at least one released source are present. It reports only provider-neutral assurance fields.
