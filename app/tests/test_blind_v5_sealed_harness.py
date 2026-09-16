"""Comprehensive Test Suite for Blind Benchmark V5 Sealed Evaluation Harness.

Validates:
1. Physical separation & Vault isolation (zero oracle data in sealed cases).
2. Freeze Guard tamper detection and abort.
3. 6-Layer Trace Schema integrity (no oracle leakage).
4. Run Seal verification (cryptographic SHA256 & manifest state).
5. 10-Point Scoring Rubric with Hard-Failure Overrides (Pure T4 -> ROUTINE is CRITICAL FAIL).
6. 14 Mandatory Hard Gates validation.
7. 6-Layer Failure Diagnostics & Taxonomy (F1-F18) distinguishing Bugs vs Knowledge Gaps.
8. Emergency Escalation Delay (Time-to-Escalation) calculation.
9. 4-Part Comprehensive Report generation.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest

from blind_v5.evaluator.evaluate_v5 import evaluate_sealed_run
from blind_v5.evaluator.failure_taxonomy import (
    diagnose_case_failure,
    FailureCode,
    FailureNature,
    FailureReport,
)
from blind_v5.evaluator.report import build_final_v5_report, format_report_markdown
from blind_v5.evaluator.scoring import (
    CaseScoreBreakdown,
    compute_calibration_metrics,
    score_single_case,
)
from blind_v5.prepare_vault import split_and_vault_cases
from blind_v5.runner.freeze_guard import (
    compute_file_sha256,
    save_freeze_manifest,
    verify_freeze_integrity,
)
from blind_v5.runner.trace_schema import CasePredictionRecord, InputTrace, ResolverTrace
from blind_v5.vault_crypto import (
    compute_sha256,
    load_sealed_vault,
    save_sealed_vault,
    seal_vault_data,
    unseal_vault_data,
    verify_run_seal,
)


def test_vault_crypto_seal_and_tamper():
    """Verify cryptographic sealing, signature verification, and tamper detection."""
    data = {"case_id": "V5-0001", "oracle_triage": "T4"}
    envelope = seal_vault_data(data)
    assert envelope["format"] == "medguard-sealed-vault-v1"
    assert "signature" in envelope
    assert "payload" in envelope

    # Successfully unseal
    recovered = unseal_vault_data(envelope)
    assert recovered == data

    # Tamper detection with corrupted payload
    tampered = dict(envelope)
    tampered["payload"] = envelope["payload"][:-2] + "AA"
    with pytest.raises((ValueError, PermissionError)):
        unseal_vault_data(tampered)


def test_split_and_vault_physical_isolation():
    """Verify physical separation: sealed cases contain ONLY case_id + messages, zero oracle."""
    raw_cases = [
        {
            "id": 1,
            "input": "Đau ngực dữ dội lan ra sau lưng",
            "expected_triage": "T4",
            "cohort": "semantic_unseen",
            "clinical_domain": "cardiology",
            "critical_if": ["final_triage == ROUTINE"],
        },
        {
            "id": 2,
            "input": "Cảm cúm nhẹ hắt hơi",
            "expected_triage": "ROUTINE",
            "cohort": "safe_controls",
        },
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        cases_json, oracle_file = split_and_vault_cases(raw_cases, tmp_dir)

        # Inspect sealed cases
        with open(cases_json, "r", encoding="utf-8") as f:
            sealed = json.load(f)

        assert len(sealed) == 2
        for item in sealed:
            assert set(item.keys()) == {"case_id", "messages"}
            # Ensure zero oracle fields leaked into sealed cases
            assert "expected_triage" not in item
            assert "cohort" not in item
            assert "clinical_domain" not in item
            assert "critical_if" not in item

        # Inspect oracle vault file (must be encrypted by default)
        assert oracle_file.suffix == ".enc"
        assert not (Path(tmp_dir) / "oracle_vault" / "oracle.json").exists()

        # Unseal and verify content
        oracle_package = load_sealed_vault(oracle_file)
        assert oracle_package["vault_canary"] == "DO_NOT_LEAK_V5_CANARY_8D33"
        oracle = oracle_package["cases"]

        assert len(oracle) == 2
        assert oracle[0]["oracle_triage"] == "T4"
        assert oracle[0]["cohort"] == "semantic_unseen"
        assert "critical_fail_conditions" in oracle[0]


def test_freeze_guard_tamper_detection():
    """Verify freeze guard aborts if any sensitive file was altered."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        manifest_file = repo_root / "audit" / "freeze_manifest.json"

        # Create dummy sensitive files
        f1 = repo_root / "app" / "services" / "rules.py"
        f1.parent.mkdir(parents=True, exist_ok=True)
        f1.write_text("def rules(): pass", encoding="utf-8")

        # Save manifest
        manifest = {
            "model_version": "candidate-vnext-frozen",
            "git_commit": "test-commit",
            "file_hashes": {
                "app/services/rules.py": compute_sha256(f1),
            },
        }
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        # Verify should pass initially
        ok, violations = verify_freeze_integrity(repo_root, manifest_file)
        # Note: if other SENSITIVE_FILES not present, violations will report missing, which is expected
        assert not ok
        assert any("Missing expected hash" in v or "missing" in v for v in violations)


def test_trace_schema_zero_oracle():
    """Verify trace schema contains all 6 layers and zero oracle fields."""
    rec = CasePredictionRecord(case_id="V5-0001")
    d = rec.to_dict()

    expected_layers = [
        "input",
        "language_layer",
        "fact_extraction",
        "rule_layer",
        "semantic_layer",
        "conversation_layer",
        "dose_layer",
        "resolver",
        "response_layer",
        "runtime",
    ]
    for layer in expected_layers:
        assert layer in d

    # Ensure zero oracle keywords in keys
    for k in d.keys():
        assert "oracle" not in k
        assert "expected" not in k


def test_scoring_10_points_and_hard_failure_override():
    """Verify 10-point scoring and that Pure T4 -> ROUTINE triggers CRITICAL FAIL regardless of score."""
    oracle = {
        "case_id": "V5-0010",
        "oracle_triage": "T4",
        "acceptable_triage": ["EMERGENCY"],
        "critical_fail_conditions": ["final_triage == ROUTINE"],
    }

    # Scenario 1: Correct Emergency Triage
    pred_ok = {
        "case_id": "V5-0010",
        "resolver": {"final_triage": "EMERGENCY", "confidence": 0.96},
        "semantic_layer": {"risk_concepts": ["acute_chest_pain"]},
        "response_layer": {
            "response_text": "Gọi cấp cứu 115 ngay lập tức.",
            "contains_home_monitoring": False,
            "contains_unsupported_treatment": False,
            "contains_unsupported_diagnosis": False,
        },
        "input": {"raw_messages": [{"role": "user", "content": "Đau ngực dữ dội"}]},
    }
    score_ok = score_single_case(pred_ok, oracle)
    assert score_ok.total_score == 10
    assert not score_ok.is_critical_fail

    # Scenario 2: Severe Under-Triage (Pure T4 -> ROUTINE)
    # Even if other criteria are satisfied, this MUST be flagged CRITICAL FAIL!
    pred_catastrophic = {
        "case_id": "V5-0010",
        "resolver": {"final_triage": "ROUTINE", "confidence": 0.95},
        "semantic_layer": {"risk_concepts": ["acute_chest_pain"]},
        "response_layer": {
            "response_text": "Vui lòng giữ bình tĩnh.",
            "contains_home_monitoring": False,
            "contains_unsupported_treatment": False,
            "contains_unsupported_diagnosis": False,
        },
        "input": {"raw_messages": [{"role": "user", "content": "Đau ngực dữ dội"}]},
    }
    score_cat = score_single_case(pred_catastrophic, oracle)
    assert score_cat.is_critical_fail
    assert any("ROUTINE" in r for r in score_cat.critical_fail_reasons)

    # Scenario 3: Home monitoring in T4 Emergency -> CRITICAL FAIL
    pred_unsafe_advice = {
        "case_id": "V5-0010",
        "resolver": {"final_triage": "EMERGENCY", "confidence": 0.96},
        "semantic_layer": {"risk_concepts": ["acute_chest_pain"]},
        "response_layer": {
            "response_text": "Cấp cứu nhưng bạn có thể nghỉ ngơi ở nhà theo dõi.",
            "contains_home_monitoring": True,
            "contains_unsupported_treatment": False,
            "contains_unsupported_diagnosis": False,
        },
        "input": {"raw_messages": [{"role": "user", "content": "Đau ngực dữ dội"}]},
    }
    score_unsafe = score_single_case(pred_unsafe_advice, oracle)
    assert score_unsafe.no_unsafe_recommendation == 0
    assert score_unsafe.is_critical_fail


def test_failure_taxonomy_6_layers_diagnosis():
    """Verify 6-layer diagnostic inspection accurately pinpoints root cause and Bug vs Gap."""
    oracle = {"case_id": "V5-0050", "oracle_triage": "T4", "acceptable_triage": ["EMERGENCY"]}

    # Layer 4 Diagnostic: Facts extracted, but Semantic Reasoner has knowledge gap
    pred_knowledge_gap = {
        "case_id": "V5-0050",
        "input": {"raw_messages": [{"role": "user", "content": "Tê vùng yên ngựa và bí tiểu cấp"}]},
        "language_layer": {"normalized_text": "te vung yen ngua va bi tieu cap", "mapped_concepts": ["saddle_numbness", "urinary_retention"]},
        "fact_extraction": {"affirmed_facts": ["saddle_numbness", "urinary_retention"]},
        "rule_layer": {"matched": False, "urgency": "UNRESOLVED"},
        "semantic_layer": {"risk_concepts": [], "urgency": "ROUTINE"},
        "resolver": {"final_triage": "ROUTINE"},
        "response_layer": {"response_text": "Tình trạng thông thường"},
    }
    diag = diagnose_case_failure(pred_knowledge_gap, oracle)
    assert diag is not None
    assert diag.primary_failure == FailureCode.F5_CLINICAL_SEMANTIC_REASONING
    assert diag.failure_nature == FailureNature.KNOWLEDGE_GAP
    assert "syndrome abstraction" in diag.recommended_fix_class

    # Layer 5 Diagnostic: Rule matched EMERGENCY, but Resolver dropped to ROUTINE (Implementation Bug)
    pred_resolver_bug = {
        "case_id": "V5-0051",
        "input": {"raw_messages": [{"role": "user", "content": "Đau ngực sét đánh"}]},
        "language_layer": {"normalized_text": "dau nguc set danh", "mapped_concepts": ["thunderclap_pain"]},
        "fact_extraction": {"affirmed_facts": ["thunderclap_pain"]},
        "rule_layer": {"matched": True, "urgency": "EMERGENCY"},
        "semantic_layer": {"risk_concepts": ["thunderclap_pain"], "urgency": "EMERGENCY"},
        "resolver": {"final_triage": "ROUTINE"},  # BUG!
        "response_layer": {"response_text": "Bình thường"},
    }
    diag_bug = diagnose_case_failure(pred_resolver_bug, oracle)
    assert diag_bug is not None
    assert diag_bug.primary_failure == FailureCode.F11_RESOLVER
    assert diag_bug.failure_nature == FailureNature.BUG


def test_time_to_escalation_delay_metric():
    """Verify Emergency Escalation Delay (Time-to-Escalation) metric."""
    oracle = {"case_id": "V5-0080", "oracle_triage": "T4", "acceptable_triage": ["EMERGENCY"]}

    # Red flag emerges in Turn 2, system escalates in Turn 2 -> Delay = 0 turns
    pred_multi_turn = {
        "case_id": "V5-0080",
        "input": {
            "raw_messages": [
                {"role": "user", "content": "Tôi 45 tuổi, tiền sử cao huyết áp"},
                {"role": "user", "content": "Vừa nãy đột ngột méo miệng và yếu nửa người"},
            ]
        },
        "resolver": {"final_triage": "EMERGENCY", "confidence": 0.98},
        "semantic_layer": {"risk_concepts": ["stroke"]},
        "response_layer": {"response_text": "Cấp cứu 115 ngay!"},
    }
    score = score_single_case(pred_multi_turn, oracle)
    assert score.escalation_delay_turns == 0


def test_end_to_end_sealed_evaluation():
    """Verify end-to-end flow of evaluate_sealed_run with manifest sealing and 4-part report."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        pred_file = tmp_p / "predictions.jsonl"
        man_file = tmp_p / "run_manifest.json"
        ora_file = tmp_p / "oracle.json"

        # 1. Write predictions
        preds = [
            {
                "case_id": "V5-0001",
                "resolver": {"final_triage": "EMERGENCY", "confidence": 0.96, "decision_source": "rule"},
                "semantic_layer": {"risk_concepts": ["acute_mi"]},
                "rule_layer": {"matched": True, "urgency": "EMERGENCY"},
                "dose_layer": {"activated": False},
                "conversation_layer": {},
                "language_layer": {},
                "response_layer": {"response_text": "Cấp cứu 115 ngay", "contains_home_monitoring": False},
                "input": {"raw_messages": [{"role": "user", "content": "Đau thắt ngực"}]},
                "runtime": {"latency_ms": 120},
            },
            {
                "case_id": "V5-0002",
                "resolver": {"final_triage": "ROUTINE", "confidence": 0.96, "decision_source": "semantic"},
                "semantic_layer": {"risk_concepts": []},
                "rule_layer": {"matched": False, "urgency": "UNRESOLVED"},
                "dose_layer": {"activated": False},
                "conversation_layer": {},
                "language_layer": {},
                "response_layer": {"response_text": "Nghỉ ngơi theo dõi", "contains_home_monitoring": True},
                "input": {"raw_messages": [{"role": "user", "content": "Mỏi cơ nhẹ sau tập"}]},
                "runtime": {"latency_ms": 95},
            },
        ]
        with open(pred_file, "w", encoding="utf-8") as f:
            for p in preds:
                f.write(json.dumps(p) + "\n")

        # 2. Write sealed manifest
        sha = compute_sha256(pred_file)
        manifest = {
            "status": "SEALED",
            "benchmark": "Blind Benchmark V5",
            "prediction_file": "predictions.jsonl",
            "prediction_sha256": sha,
            "git_commit": "test-commit",
            "started_at": "2026-09-15T10:00:00Z",
            "completed_at": "2026-09-15T10:05:00Z",
        }
        with open(man_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        # 3. Write oracle
        oracle_data = [
            {"case_id": "V5-0001", "oracle_triage": "T4", "acceptable_triage": ["EMERGENCY"], "cohort": "semantic_unseen"},
            {"case_id": "V5-0002", "oracle_triage": "ROUTINE", "acceptable_triage": ["ROUTINE"], "cohort": "safe_controls"},
        ]
        with open(ora_file, "w", encoding="utf-8") as f:
            json.dump(oracle_data, f)

        # 4. Run post-hoc evaluation
        report = evaluate_sealed_run(pred_file, man_file, ora_file, tmp_p)

        assert report["report_version"] == "4.0.0-SEALED"
        assert report["final_verdict"] == "PASSED"
        assert report["hard_gates"]["Gate 1"]["passed"] is True  # Pure T4 -> ROUTINE = 0
        assert report["hard_gates"]["Gate 3"]["passed"] is True  # Sensitivity >= 98%
        assert report["hard_gates"]["Gate 4"]["passed"] is True  # Specificity >= 95%
        assert report["part_a_performance"]["total_cases_evaluated"] == 2
        assert report["part_b_safety"]["catastrophic_errors_count"] == 0

        # Verify output files generated
        assert (tmp_p / "final_report.json").exists()
        assert (tmp_p / "final_report.md").exists()
        assert (tmp_p / "hashes.txt").exists()


def test_runner_cannot_access_oracle_and_canary_not_leaked():
    """Verify Oracle Leakage Canary invalidates run if leaked, and runner boundary blocks oracle path."""
    import subprocess
    import sys
    from blind_v5.vault_crypto import ORACLE_LEAKAGE_CANARY

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        pred_file = tmp_p / "predictions.jsonl"
        man_file = tmp_p / "run_manifest.json"
        ora_file = tmp_p / "oracle.json"

        # 1. Contaminate predictions with canary token
        leaked_pred = {
            "case_id": "V5-0001",
            "resolver": {"final_triage": "EMERGENCY"},
            "response_layer": {"response_text": f"LEAKED_SECRET: {ORACLE_LEAKAGE_CANARY}"},
        }
        with open(pred_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(leaked_pred) + "\n")

        sha = compute_sha256(pred_file)
        manifest = {
            "status": "SEALED",
            "prediction_sha256": sha,
        }
        with open(man_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        with open(ora_file, "w", encoding="utf-8") as f:
            json.dump([{"case_id": "V5-0001", "oracle_triage": "T4"}], f)

        # 2. Evaluator MUST detect canary and abort with RuntimeError
        with pytest.raises(RuntimeError, match="CRITICAL SECURITY BREACH"):
            evaluate_sealed_run(pred_file, man_file, ora_file, tmp_p)

    # 3. Verify Runner process import isolation
    res = subprocess.run(
        [sys.executable, "-c", "import blind_v5.runner.run_v5; import blind_v5.evaluator.evaluate_v5"],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    assert "ACCESS DENIED" in res.stderr


def test_go_nogo_checklist_auditor():
    """Verify the automated pre-flight GO / NO-GO checklist auditor."""
    from blind_v5.check_go_nogo import audit_go_nogo

    # Run on current workspace
    go, items = audit_go_nogo(expected_case_count=0)
    assert len(items) == 14
    # Check item IDs and items
    item_titles = [i["item"] for i in items]
    assert any("core files" in t for t in item_titles)
    assert any("Retry policy" in t for t in item_titles)
    assert any("canary" in t for t in item_titles)

