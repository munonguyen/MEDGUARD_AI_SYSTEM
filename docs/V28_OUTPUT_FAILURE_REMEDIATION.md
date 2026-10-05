# V28 output failure remediation

The 60-case output gate remains fail-closed. A high average score, local policy retrieval, or a passing unit suite cannot override failed case checks or pending clinical approval.

## Implemented corrections

- Refine only isolated generic chest-keyword candidates before severity-max resolution. The V28 contextual assessment may apply only when breathlessness, sweating and radiation are explicitly denied, with no independent severe/persistent/rest symptoms or relevant cardiac history. Unspecified associated symptoms remain unknown. Emergency vitals and historical safety floors remain authoritative.
- Apply the same bounded assessment to the legacy rule engine, semantic syndrome detector and exertion lattice. Preserve explicit changes from initially absent symptoms to present symptoms.
- Present the contextual action, one question that changes management, and conditional emergency instructions instead of unrelated generic hypotheses. Sources: NHS chest pain and angina. This implementation still needs independent clinical review.
- Index the real monitoring-rule thresholds/details rather than a nonexistent nested thresholds field; index medication-incident policies with their pending approval provenance; retain source URLs across retrieval result copies.

## Remaining evidence requirements

| Finding | Required resolution | Gate policy |
|---|---|---|
| MRQ-033 pregnancy pain plus bleeding: urgent label versus emergency runtime | Independent clinicians must assess severity, gestation, bleeding amount, faintness and missing information; sign an adjudication record | Do not change the fixture to match output or lower urgency merely to pass |
| Post-hoc grounding failures | Trace claims to retrieved source passages, reported patient facts or explicitly verified calculations; distinguish runtime provenance from post-hoc lookup | Keep thresholds and unsupported-claim flags |
| Real model unavailable | Run writer/reviewer on the actual configured gateway; capture request model/version, verification status, sources and latency | Mock provider tests and fallback are not real-model evidence |
| Production promotion blocked | Complete the promotion manifest, source review, clinician adjudication and deployment/security evidence | No push or promotion while required gates fail |
| Ada/Buoy superiority untested | Sealed matched-case comparison with blinded clinical reviewers and predefined safety/quality/length metrics | Do not claim superiority |

## Reproducible verification

Run `.venv/bin/pytest -q app/tests/` and `.venv/bin/python scripts/audit_v28_output_quality.py`. The latter intentionally exits nonzero while any software output condition fails. Run `frontend/tests/chest-calibration-ui.mjs` against the local API for three scenarios on desktop and mobile. Reports must include the exact question, visible answer, raw API response, source commit, remaining failures and gateway status. Preserve the original dataset checksum and baseline results.
