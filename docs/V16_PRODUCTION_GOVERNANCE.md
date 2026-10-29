# V16 Production Governance

## Scope

V16 turns the V15 adaptive runtime from an implementation feature into an explicit deployment contract. It does not change clinical severity authority or patient-facing generation ownership.

## Adaptive routing readiness

`GET /v1/health/readiness` now includes `adaptive_routing_governance` as a production-required check.

Accepted states:

- `disabled`: PASS — adaptive routing is explicitly off.
- `shadow`: PASS — Kev may be observed but cannot affect execution routing.
- `enforced`: PASS only when a real Kev endpoint is configured, calibration status is `validated`, a calibration version is present, and the runtime effective mode is actually `enforced`.

The check fails when:

- the adaptive mode is invalid;
- `enforced` is requested without `MEDGUARD_KEV_URL`;
- `enforced` is requested with an unvalidated or unversioned Kev calibration;
- requested/effective modes disagree.

This is intentionally stricter than the V15 runtime guard. V15 fails safe by degrading an uncalibrated real Kev to `shadow`; V16 additionally makes the operator-visible configuration mismatch block production readiness.

## Output-quality release benchmark

`scripts/benchmark_professional_response.py` provides a deterministic behavioral benchmark for patient-facing release policy. It uses communication/safety behavior labels, not diagnoses as clinical gold labels.

The benchmark includes acceptable examples for ROUTINE, URGENT, EMERGENCY, exposure reaction and medication-safety communication, plus rejection examples for:

- generic boilerplate;
- false reassurance;
- diagnostic overclaim;
- internal routing/agent jargon;
- emergency follow-up questions before action;
- emergency action delayed to a later block;
- watch-and-wait language in an emergency.

Release threshold:

- classification accuracy = 100% on the versioned behavioral set;
- false accepts = 0;
- false rejects = 0;
- critical failures = 0;
- average score of accepted-good cases >= 0.95.

## Continuous validation

`continuous_validation.py` now includes the professional-response benchmark in the common gate and explicitly requires zero critical false accepts for the production profile.

This complements, rather than replaces:

- full pytest regression;
- medical-quality regressions;
- triage under-triage/emergency-recall gates;
- adversarial fail-closed gates;
- LLM control-plane checks;
- runtime performance gates;
- OCR and external-dataset production gates;
- `/health/readiness` production checks.

## Clinical validation boundary

Passing V16 is an engineering release criterion, not a claim that the system is clinically validated. Promotion to clinical production still requires live-model evaluation, deidentified shadow data, clinician review/approval, external dataset evidence, provider/privacy controls, and the existing production readiness requirements.