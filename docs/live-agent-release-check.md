# Live agent release check

`scripts/check_llm_gateway.py --probe-models` proves model aliases are reachable, not that the complete MedGuard Writer/Reviewer and clinical quality gates passed. The additional command below exercises the deployed `/v1/chat` path with three synthetic turns in one conversation: chest-pain emergency, toothache, then reported appendix pain. It makes model calls and writes synthetic conversation history under the configured tenant.

Supply these environment variables through the deployment's secret/configuration system:

| Variable | Purpose |
| --- | --- |
| `MEDGUARD_API_URL` | MedGuard application origin (not the LiteLLM gateway); an optional `/v1` suffix is accepted |
| `MEDGUARD_API_KEY` | Application API credential |
| `MEDGUARD_TENANT_ID` | Authorized test tenant |
| `MEDGUARD_CONSENT_TOKEN` | Accepted consent evidence for synthetic tests |

Run:

```bash
python scripts/check_agent_release.py
```

Exit 0 requires verified origin, completed Writer and Reviewer traces, narrative and assurance, correct emergency/episode behavior and full production readiness. Exit 1 indicates a transport, contract, content, verification or readiness failure. Exit 2 means required configuration is missing. Output includes request IDs, stage statuses, disposition and safe failure codes; it does not print raw clinical answers, credentials or provider error messages. Use request IDs to inspect private audit records.

The automated tests use `httpx.MockTransport`; they establish checker behavior only. A successful mock test never substitutes for running this command against the deployed application. Production readiness may correctly fail because clinical knowledge, external evidence or infrastructure is not approved/ready. Keep those gates enabled.

## OCR correction

Six older OCR tests passed only a PNG header while declaring it a valid image. They now share a complete synthetic 1×1 PNG. An additional control verifies truncated PNG rejection. Pillow is pinned to the installed/tested version in runtime dependencies; absence of the full validator fails closed with `image_validation_unavailable`, rather than admitting an image based only on its header. OCR engines still fail closed when unavailable. No mock OCR results are introduced into production.

## Current limitation

Validation: the full backend run passed **967 tests with no exclusions**. The final focused OCR/release-check run passed **51 tests**, including two additional checker configuration/redaction controls added after broad test collection. `git diff --check` passed. The checker itself exits 2 in this workspace because the four required application environment variables are absent; this is a blocked live check, not a live success.

The workspace has no application endpoint/credentials or gateway URL/key configured. The live checker correctly exits 2 and cannot certify a real deployment. Configuration of an actual target, approved clinical evidence and a separate production load test are still needed. The per-process agent admission bound added previously prevents an unbounded queue but is not a cluster capacity certification.
