import pytest
from app.tests.public_output_fixture import passing_public_output
from scripts.public_output_evidence import summarize_public_output_audit


@pytest.mark.parametrize('defect', ['stale', 'dirty', 'missing', 'duplicate', 'answer', 'strict', 'professional', 'jury'])
def test_public_output_gate_blocks_missing_stale_or_failed_real_case_evidence(defect):
    audit = passing_public_output('candidate')
    row = audit['results'][0]
    if defect == 'stale': audit['provenance']['commit'] = 'old'
    if defect == 'dirty': audit['provenance']['working_tree_diff_sha256'] = 'changes'
    if defect == 'missing': audit['results'].pop()
    if defect == 'duplicate': row['case_id'] = audit['results'][1]['case_id']
    if defect == 'answer': row['raw_response'] = {}
    if defect == 'strict': row['strict_failures'] = ['actual failure']
    if defect == 'professional': row['professional_default']['passed'] = False
    if defect == 'jury': row['jury']['overall_passed'] = False
    # A forged aggregate PASS never overrides per-case failures.
    audit['summary'] = {'software_output_gate': 'PASS', 'strict_passed': 60}
    assert not summarize_public_output_audit(audit, expected_sha='candidate')['gate_passed']


def test_empty_audit_cannot_authorize_production():
    assert not summarize_public_output_audit({}, expected_sha='candidate')['gate_passed']
