"""Require actual per-case public output evidence before release promotion."""
import hashlib
import json
from pathlib import Path


def load_public_output_audit() -> dict:
    path = Path(__file__).resolve().parent.parent / 'artifacts/v28_output_audit/MedGuard_V28_Output_Audit.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def summarize_public_output_audit(audit: dict, *, expected_sha: str) -> dict:
    rows = audit.get('results', [])
    blockers = []
    provenance = audit.get('provenance') or {}
    if provenance.get('commit') != expected_sha:
        blockers.append('candidate_sha_mismatch')
    if provenance.get('working_tree_diff_sha256') != hashlib.sha256(b'').hexdigest():
        blockers.append('uncommitted_code')
    if not isinstance(rows, list) or len(rows) < 60:
        rows = rows if isinstance(rows, list) else []
        blockers.append('insufficient_cases')
    if len({r.get('case_id') for r in rows if isinstance(r, dict)}) != len(rows):
        blockers.append('duplicate_or_invalid_cases')
    strict = professional = jury = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        actual_answer = (row.get('raw_response') or {}).get('answer') or {}
        strict += bool(row.get('strict_pass') is True and row.get('strict_failures') == []
                       and row.get('http_status') == 200 and actual_answer.get('summary'))
        professional += bool(row.get('professional_default', {}).get('passed') is True
                             and row.get('professional_expanded', {}).get('passed') is True)
        jury += bool(row.get('jury', {}).get('overall_passed') is True)
    for count, label in ((strict, 'strict_output_failures'), (professional, 'professional_output_failures'),
                         (jury, 'jury_or_grounding_failures')):
        if not rows or count != len(rows):
            blockers.append(label)
    return {'code_sha': provenance.get('commit'), 'total': len(rows),
            'strict_passed': strict, 'professional_passed': professional, 'jury_passed': jury,
            'report_sha256': hashlib.sha256(json.dumps(audit, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            'gate_passed': not blockers, 'blockers': blockers}
