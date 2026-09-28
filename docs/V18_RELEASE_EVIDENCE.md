# V18 Release Evidence Manifest

`release_evidence.json` is a machine-readable snapshot of the evidence attached to one MedGuard release candidate. It does not grant clinical approval and it does not replace external operational evidence.

## Generate evidence

```bash
python scripts/generate_release_evidence.py --output release_evidence.json
```

The command runs the current medical-response and professional-response engineering benchmarks, captures the readiness snapshot, records the code SHA, safe model aliases, adaptive-routing/Kev calibration metadata, independent clinical-review metadata, release blockers, and a SHA-256 integrity digest.

To make a deployment job fail unless every software and external approval gate represented by the application is satisfied:

```bash
python scripts/generate_release_evidence.py \
  --output release_evidence.json \
  --require-production-eligible
```

The current repository is expected to fail `--require-production-eligible` while independent clinician review is pending. That is a deployment safeguard, not an application regression.

## Evidence contract

A candidate may report `production_release_eligible=true` only when all of the following are simultaneously true:

- `/v1/health/readiness` reports `production_ready=true`;
- the 40-case medical-response engineering benchmark passes;
- the deterministic professional-response benchmark passes;
- independent clinical validation is `approved`, `production_evaluable=true`, and carries a versioned approval identifier;
- no production-required readiness check remains failed.

The manifest intentionally records model aliases and calibration identifiers, never API keys, provider secrets, tenant keys, HMAC secrets, or master encryption keys.

## Integrity

`evidence_digest` is SHA-256 over canonical JSON excluding the digest field itself. `validate_release_evidence()` rejects a manifest whose contents were modified after generation.

The digest proves content integrity only. It is not a digital signature and does not prove who approved a release. A production organization should sign or attest the generated artifact in its deployment/signing system and retain that attestation with the release.

## Remaining external evidence

Some production evidence cannot be manufactured by repository code and must remain external: clinician signatures, backup/restore exercises, Redis persistence/failover evidence, S3 retention/lifecycle evidence, secret rotation records, provider data-processing approval, live gateway/model shadow-set evaluation, OCR model checksums and real deployment monitoring evidence.
