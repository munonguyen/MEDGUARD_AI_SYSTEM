# V19 External Production Evidence Registry

The repository can verify external deployment evidence, but it cannot manufacture that evidence. `governance/external_evidence_registry.json` therefore starts intentionally empty and production remains blocked until real artifacts are registered.

## Validate

```bash
python scripts/validate_external_evidence.py
python scripts/validate_external_evidence.py --json
```

The validator exits non-zero until every required evidence category has at least one current approved record.

## Required evidence categories

- database backup/restore exercise
- database tenant-isolation verification
- Redis persistence/failover exercise
- queue dead-letter alerting evidence
- object-storage lifecycle/deletion evidence
- secret-rotation evidence
- consent-system evidence
- OCR model checksum/integrity evidence
- multi-replica rate-limit validation
- observability/SLO evidence
- security testing evidence
- disaster-recovery evidence
- provider data-control approval
- live agent shadow-evaluation evidence

## Record contract

Every accepted record must include:

```json
{
  "evidence_type": "database_backup_restore",
  "evidence_id": "backup-restore-2026-09-v1",
  "status": "approved",
  "artifact_sha256": "<64 hex characters>",
  "issued_at": "2026-09-20T00:00:00Z",
  "expires_at": "2026-10-20T00:00:00Z",
  "approved_by_ref": "ops-board-2026-09"
}
```

`artifact_sha256` binds the registry record to the retained external report/artifact. The registry itself also has `registry_digest`, a SHA-256 over canonical JSON excluding the digest field.

## Fail-closed rules

A category remains blocked when its record is missing, pending/rejected, missing a version/id, has an invalid artifact checksum, was issued in the future, has no usable expiry, has expired, or when the registry digest no longer matches.

The digest is an integrity check, not a digital signature. Organizations should retain signed/attested external reports in their controlled evidence system; this repository stores only non-secret references and hashes.
