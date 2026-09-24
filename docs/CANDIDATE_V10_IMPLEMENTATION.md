# MedGuard Candidate V10 — Implementation and Pre-Blind Evidence

## Status

**MedGuard Candidate V10 — FROZEN FOR INDEPENDENT BLIND V10 ONE-SHOT
VALIDATION.** Historical regression and mechanism validation passed. Clinical
generalization on unseen V10 has not been confirmed. Blind V10 has not been
generated or executed in this repository.

Immutable identities:

- `v10-candidate-core`: production clinical core.
- `v10-blind-frozen`: evaluator, one-shot protocol and provenance attestation.

`datasets/active_learning/captured_cases.json` is pre-existing mutable
telemetry and is excluded from both candidate and freeze scope.

## Architectural changes

1. `clinical_safety_floor.py` aggregates evidence strength, clinical threat,
   severe toxidrome routing, physiologic consequences, and end-organ coupling.
   Its disposition is monotonic: downstream policy may escalate but may not
   return a lower triage level.
2. OOD evaluation now runs after the clinical safety floor is available. An
   emergency floor revokes OOD downgrade/refusal authority. Purely non-medical
   content is still handled by the normal OOD guard.
3. `toxicology_signature_router.py` recognizes severe syndromic toxidromes
   without requiring a named toxin, while retaining local-negation controls.
4. `dual_crisis_policy.py` independently retains medical-emergency and
   crisis-support flags. Medical emergency instructions precede psychological
   crisis resources in the composed response.
5. `end_organ_coupling.py` requires high-specificity combinations for severe
   hypertension plus acute end-organ findings and recognizes indirect acute
   neurologic, intracranial, meningeal, airway-bleeding, button-battery,
   hearing-loss, and symptomatic-arrhythmia threats.
6. `response_safety.py` evaluates dangerous response content separately from
   the triage label, removing the former Gate 1/Gate 6 double count.

Gate 3 Jev was not modified. `jev_engine.py` and `jev_governance.py` match the
V9 freeze hashes byte-for-byte.

## Evaluator reconciliation

The V10 evaluator reports the following metrics independently:

- Cohort BAC benign specificity versus global benign specificity.
- SCC strict pair accuracy versus SCC case-level accuracy.
- Pure-T4 triage under-triage versus unsafe patient-facing response content.

The pre-declared gates are B10-G1 through B10-G14 in
`blind_v10/evaluator/evaluate_v10.py`. B10-G8 through B10-G12 directly measure
the V10 mechanisms: OOD emergency bypass, unnamed toxidromes, dual-crisis
composition, end-organ coupling and negative-twin semantic contrast. Cohort
counts are part of the frozen contract, so missing cohorts cannot pass through
empty-denominator defaults.

The evaluator additionally reports OOD, toxicology and end-organ benign
specificity plus dual-crisis false activation rate because the historical
specificity margin is only 0.29 percentage points above the 95% threshold.

Jev reporting retains `without_jev`, `with_jev`, wrong-to-correct,
correct-to-wrong, prevented/induced undertriage and prevented/induced
overtriage. The runner labels Jev as counterfactual-only because Jev is not in
the production resolver path; no provenance field claims otherwise.

## Pre-freeze evidence

### Four mechanism benchmarks

`outputs/v10_mechanism_benchmarks_report.json`

| Benchmark | Cases | Passed | Accuracy |
|---|---:|---:|---:|
| A — OOD Emergency Bypass | 50 | 50 | 100% |
| B — Named/Unnamed Severe Toxidromes | 50 | 50 | 100% |
| C — Dual Crisis Composition | 30 | 30 | 100% |
| D — End-Organ Coupling & Stroke Deficits | 50 | 50 | 100% |
| **Total** | **180** | **180** | **100%** |

### Unified V1–V9 regression

`outputs/v10_regression_2400_report.json`

- Total cases: 2,400.
- Pure T4: 1,471/1,471 EMERGENCY (100%).
- Pure T4 to URGENT: 0.
- Pure T4 to ROUTINE: 0.
- Non-emergency specificity: 789/828 = 95.29%.
- Unsafe response content: 0.
- System errors: 0.

### Automated tests

- Full application suite: 396 passed.
- Candidate V10/freeze focused suite after freezing: 8 passed.
- Remaining warnings are two upstream Starlette/httpx deprecation warnings.

## Freeze and one-shot boundary

`blind_v10/freeze_manifest.json` hashes the production clinical core, frozen
evaluator, runner/protocol and both pre-blind reports. It records the core and
audit commit IDs plus report SHA-256 values. `freeze_manifest_sha256` is the
SHA-256 of the canonical manifest payload excluding that self-hash field; this
avoids an impossible recursive hash while still detecting every other manifest
change. The annotated `v10-blind-frozen` tag points to the provenance commit
whose parent is the recorded audit baseline.

Before independent execution, run `blind_v10/freeze_guard.py --verify` and the
GO/NO-GO audit. The oracle-isolated runner requires exactly 300 cases, rejects
oracle/cohort fields recursively, refuses a non-empty output directory, saves
the cases hash, records the full V10 trace, and seals predictions with SHA-256
and an evaluator-supplied HMAC. Do not tune against unseen cases or retry
clinical misclassifications.
