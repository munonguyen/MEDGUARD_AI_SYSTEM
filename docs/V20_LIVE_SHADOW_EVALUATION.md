# V20 Live Agent Shadow Evaluation

This harness exercises a deployed MedGuard `/v1/chat` path with synthetic or deidentified evaluation-only cases. It is intended to generate real gateway evidence for Writer/Reviewer behavior, fallback, citations and latency without using patient production traffic.

## Requirements

The dataset must explicitly set `training_allowed=false` and identify its source as synthetic or deidentified. A deployed MedGuard API URL, tenant-scoped API key and consent token are required. The harness refuses to fabricate a live result when those credentials are absent.

```bash
export MEDGUARD_SHADOW_BASE_URL=https://medguard-shadow.example
export MEDGUARD_SHADOW_API_KEY=...
export MEDGUARD_SHADOW_TENANT_ID=shadow-eval
export MEDGUARD_SHADOW_CONSENT_TOKEN=...

python scripts/run_live_agent_shadow_evaluation.py \
  --output live_shadow_report.json
```

Secrets are used only in request headers and are never written to the report.

## Recorded evidence

The report records the code SHA, evaluation dataset version/governance metadata, configured Writer/Reviewer aliases, gateway-verified rate, deterministic fallback rate, reviewer/provider failures, emergency under-triage, forbidden-content hits, missing citations on verified outputs, verification-status contract violations, and p50/p95 latency. The report has a SHA-256 integrity digest.

## Promotion boundary

`promotion_eligible` is hard-coded to `false` and the report validator rejects any machine-generated report that claims otherwise, even when its digest is recomputed. Passing the machine gate only means that no machine-checkable safety invariant in the selected evaluation cases failed.

Model/routing promotion still requires independent clinician review, approved provider/data controls, and a separately authorized release decision. A passing report may be hashed and referenced by the V19 `live_agent_shadow_evaluation` external-evidence record after those external approvals occur.

## Machine gate

The machine gate fails on emergency under-triage, forbidden answer content, verified gateway outputs without citations, or invalid verification-state values. Safe deterministic fallback after a provider/reviewer failure is recorded as degradation but does not itself become clinical failure; the production evidence registry and readiness policy decide whether that degradation rate is acceptable for release.
