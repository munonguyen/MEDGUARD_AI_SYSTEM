# V15 Adaptive Agent Runtime

## Purpose

V15 adds adaptive execution to the V14 single-path Writer -> Reviewer architecture without transferring clinical authority to Kev, Jev, model routing, or provider fallback.

The key separation is:

- **Clinical decision plane:** deterministic safety floor + structured clinical reasoner own patient facts, red flags, urgency, and locked actions.
- **Execution plane:** adaptive routing chooses which response agent/model tier executes and how much token budget it receives.
- **Quality plane:** Reviewer is mandatory and non-authoring; deterministic professional/safety gates can still reject an approved model draft.

## Runtime flow

```text
User / active clinical episode
        |
        v
Clinical task + safety/clinical result
        |
        +---- explicit EMERGENCY lock --------------------+
        |                                                  |
        v                                                  v
Compact PHI-minimized Kev state                       DEEP / emergency path
        |
        v
Kev advisory choice + score + confidence + margin
        |
        v
Authority-safe resolver
        |
        +--> ROUTINE / FAST or STANDARD
        +--> URGENT / STANDARD
        +--> EMERGENCY / DEEP
        +--> UNCERTAIN / DEEP
        +--> NON_CLINICAL / FAST (only with task-router agreement)
        |
        v
Writer model ladder (same clinical route)
        |
        v
Mandatory Reviewer model ladder
        |
        v
Deterministic professional + safety release gates
        |
        v
Verified patient-facing output or deterministic fallback
```

## Non-negotiable authority invariants

1. **Kev cannot directly upgrade or downgrade clinical severity.** A Kev disagreement, low confidence, score/choice conflict, UNKNOWN, or scope conflict routes to `UNCERTAIN`/DEEP review instead of rewriting the clinical result.
2. **Jev/Reviewer does not author patient prose and does not become a severity adjudicator.** Reviewer may approve, reject, or request one bounded Writer revision.
3. **Provider/model failure never changes severity.** The selected route stays fixed while the runtime tries the configured model ladder.
4. **Reviewer cannot be bypassed.** If every Reviewer model fails, the model draft is not released.
5. **Explicit emergency lock is non-downgradable.** Emergency Writer keeps the full configured Writer token budget.
6. **Clinical generated responses remain `NO_STORE`.** Repeated medical text is not blindly served from response cache. Safe exact caching remains limited to approved low-risk scopes.
7. **A real Kev endpoint cannot enter `enforced` mode without a versioned validated calibration marker.** An invalid enforcement request is automatically degraded to `shadow`.

## Kev calibration guard

`MEDGUARD_ADAPTIVE_ROUTING_MODE=enforced` is only effective for a configured real Kev endpoint when both conditions hold:

- `MEDGUARD_KEV_CALIBRATION_STATUS=validated`
- `MEDGUARD_KEV_CALIBRATION_VERSION=<approved-version>`

If either condition is missing, the runtime records an enforcement-guard metric and uses `shadow`. This prevents an uncalibrated checkpoint from affecting execution simply because an environment variable was changed. A missing Kev URL still uses the validated clinical fallback signal and does not require the calibration marker.

## Adaptive model ladder

Writer selection uses the route's model tier:

- `FAST` -> `MEDGUARD_FAST_WRITER_MODEL`
- `STANDARD` -> `MEDGUARD_STANDARD_WRITER_MODEL`
- `DEEP` -> `MEDGUARD_DEEP_WRITER_MODEL`

If the selected alias fails, the graph retries in order using the default clinical model and `MEDGUARD_WRITER_FALLBACK_MODELS`. All aliases are expected to be routed by LiteLLM, so aliases may point to different upstream providers.

Reviewer uses the configured primary verifier followed by `MEDGUARD_VERIFIER_FALLBACK_MODELS`. Exhausting this ladder fails safe; no unverified model draft is released.

## Token budgets

Route-aware token caps reduce routine cost while preserving high-risk capacity:

- FAST Writer: bounded by `MEDGUARD_FAST_MAX_INPUT_TOKENS` / `MEDGUARD_FAST_MAX_OUTPUT_TOKENS`.
- STANDARD Writer: bounded by `MEDGUARD_STANDARD_MAX_INPUT_TOKENS` / `MEDGUARD_STANDARD_MAX_OUTPUT_TOKENS`.
- DEEP Writer: keeps the existing global Writer budget. Emergency and uncertain routes are intentionally DEEP.
- Reviewer remains mandatory for all tiers. Reviewer output caps are controlled separately for FAST/STANDARD/DEEP.
- A missing adaptive route keeps the pre-V15 budget unchanged, protecting legacy and pharmacology paths from accidental throttling.

The gateway still performs the pre-call token estimate and fails before provider execution when the estimated input exceeds the selected route budget.

## Cache policy

Clinical intents (`triage`, `safety`, `monitoring`, `general`) remain `NO_STORE`. This prevents stale patient-specific model prose from being replayed when the apparent question text matches but the episode/context differs.

Optimization comes from:

- PHI-minimized compact routing state;
- route-aware model selection;
- route-aware token caps;
- provider/gateway prompt-prefix caching where supported;
- exact hashing of tenant/conversation/context/tool result/prompt/knowledge versions for safe cacheable scopes;
- single-flight only where policy explicitly allows exact safe reuse.

## Patient-facing quality gate

A model Reviewer approval is necessary but not sufficient. The deterministic professional-response gate rejects output for conditions including:

- generic boilerplate opening;
- missing concrete action for a resolved clinical care level;
- false reassurance;
- diagnostic overclaim language;
- missing locked safety action;
- emergency action not presented early;
- follow-up questions in an emergency response;
- emergency delay/watch-at-home language;
- leakage of internal terms such as Safety Kernel, routing decision, Kev, Jev, Writer Agent, or Reviewer Agent.

Quality telemetry includes professional response score and rejection reason counters.

## Rollout

1. Keep `MEDGUARD_ADAPTIVE_ROUTING_MODE=shadow` while collecting deidentified routing telemetry.
2. Validate Kev calibration on MedGuard-labeled routing data. Do not infer calibration from generic model confidence.
3. Register the approved calibration status/version before requesting `enforced`.
4. Exercise primary/fallback model outages in staging and verify that severity remains unchanged.
5. Run the full backend regression suite, V10 provenance guard, frontend build, V15 routing/runtime tests, and response-quality regressions.
6. Promote to `enforced` only after the routing and output-quality gates pass the agreed acceptance thresholds.

## V15 acceptance criteria

- Every clinical response remains on the V14 Writer -> Reviewer single path.
- Emergency lock cannot be downgraded.
- Kev disagreement does not directly set a new severity.
- Unvalidated real Kev cannot enter enforced mode.
- Writer model fallback succeeds without changing route when a fallback model is healthy.
- Reviewer model fallback succeeds without bypass; complete Reviewer outage fails safe.
- FAST/STANDARD token caps reach provider request controls.
- Missing adaptive route preserves the legacy budget.
- DEEP emergency Writer keeps full configured budget.
- Generic, unsafe, jargon-leaking, or emergency-delaying prose is rejected even when model Reviewer approves.
- Existing medical quality regressions, historical V10 provenance, and frontend production build remain green.
