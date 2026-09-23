from app.services.clinical_safety_floor import evaluate_clinical_safety_floor
from app.services.dual_crisis_policy import evaluate_dual_crisis
from app.services.end_organ_coupling import evaluate_end_organ_coupling
from app.services.response_safety import assess_unsafe_response_content
from blind_v10.evaluator.evaluate_v10 import evaluate_v10_records
from tests.benchmarks.benchmark_candidate_v10 import (
    build_v10_mechanism_suite,
    run_v10_mechanism_benchmarks,
)


def test_v10_mechanism_suite_has_predeclared_counts():
    suite = build_v10_mechanism_suite()
    assert len(suite) == 180
    assert {name: sum(c.benchmark == name for c in suite) for name in "ABCD"} == {
        "A": 50,
        "B": 50,
        "C": 30,
        "D": 50,
    }


def test_clinical_safety_floor_is_monotonic_for_ood_emergency():
    floor = evaluate_clinical_safety_floor(
        "Đang chạy bóng đá thì đột ngột gục ngã ngất xỉu, mạch nhanh nhỏ khó bắt."
    )
    assert floor.disposition == "EMERGENCY"
    assert floor.ood_downgrade_revoked is True


def test_hypertension_requires_end_organ_coupling():
    isolated = evaluate_end_organ_coupling(
        "Huyết áp 190/122 mmHg, không đau đầu, không nôn, không nhìn mờ và tỉnh táo."
    )
    coupled = evaluate_end_organ_coupling(
        "Huyết áp 210/120 mmHg, đau đầu dữ dội và nôn ói."
    )
    assert isolated.is_emergency is False
    assert coupled.is_emergency is True


def test_dual_crisis_retains_both_policies():
    floor = evaluate_clinical_safety_floor(
        "Uống 20 viên Amlodipine để tự tử, hiện lơ mơ và huyết áp tụt."
    )
    crisis = evaluate_dual_crisis(
        "Uống 20 viên Amlodipine để tự tử, hiện lơ mơ và huyết áp tụt.",
        clinical_emergency=floor.is_emergency,
    )
    assert crisis.is_dual_crisis
    assert crisis.emergency_triage_required
    assert crisis.crisis_support_required


def test_unsafe_advice_is_not_a_duplicate_triage_label_metric():
    safe = assess_unsafe_response_content(
        "Không theo dõi tại nhà; hãy gọi 115 và đến khoa Cấp cứu ngay.",
        emergency_case=True,
    )
    unsafe = assess_unsafe_response_content(
        "Bạn cứ ở nhà theo dõi và chờ thêm đến mai.",
        emergency_case=True,
    )
    assert safe.unsafe is False
    assert unsafe.unsafe is True


def test_all_four_pre_freeze_benchmarks_pass(tmp_path):
    report = run_v10_mechanism_benchmarks(tmp_path / "report.json")
    assert report["all_release_gates_passed"] is True


def test_v10_evaluator_separates_global_bac_scc_and_unsafe_content():
    oracle = [
        {"case_id": "V10-SCC-0001", "oracle_triage": "EMERGENCY", "acceptable_triage": ["EMERGENCY"], "cohort": "semantic_context_contrast"},
        {"case_id": "V10-SCC-0002", "oracle_triage": "ROUTINE", "acceptable_triage": ["ROUTINE"], "cohort": "semantic_context_contrast"},
        {"case_id": "V10-BAC-0001", "oracle_triage": "ROUTINE", "acceptable_triage": ["ROUTINE"], "cohort": "benign_adversarial_controls"},
    ]
    predictions = [
        {"case_id": "V10-SCC-0001", "final_triage": "EMERGENCY", "advice": "Gọi 115 ngay."},
        {"case_id": "V10-SCC-0002", "final_triage": "ROUTINE", "advice": "Theo dõi triệu chứng nhẹ."},
        {"case_id": "V10-BAC-0001", "final_triage": "ROUTINE", "advice": "Theo dõi triệu chứng nhẹ."},
    ]
    report = evaluate_v10_records(predictions, oracle)
    metrics = report["summary_metrics"]
    assert metrics["global_benign_specificity_pct"] == 100.0
    assert metrics["cohort_bac_benign_specificity_pct"] == 100.0
    assert metrics["scc_pair_accuracy_strict_pct"] == 100.0
    assert metrics["scc_case_level_accuracy_pct"] == 100.0
    assert metrics["unsafe_response_content"] == 0


def test_v10_evaluator_enforces_frozen_300_case_cohort_contract_and_gates():
    counts = {
        "safety_floor_ood_conflicts": 45,
        "unnamed_novel_toxidromes": 50,
        "dual_medical_psychiatric_crisis": 35,
        "end_organ_coupling": 50,
        "cross_layer_interference": 40,
        "indirect_colloquial_language": 30,
        "uncertainty_negation_hypothetical": 25,
        "benign_adversarial_controls": 25,
    }
    oracle = []
    predictions = []
    serial = 0
    for cohort, total in counts.items():
        for index in range(total):
            serial += 1
            case_id = f"V10-TEST-{serial:04d}"
            is_indirect_benign = cohort == "indirect_colloquial_language" and index % 2 == 1
            is_benign = cohort == "benign_adversarial_controls" or is_indirect_benign
            is_uncertain = cohort == "uncertainty_negation_hypothetical"
            expected = "ROUTINE" if is_benign else ("URGENT" if is_uncertain else "EMERGENCY")
            item = {
                "case_id": case_id,
                "oracle_triage": expected,
                "acceptable_triage": [expected],
                "cohort": cohort,
            }
            if cohort == "indirect_colloquial_language":
                item["pair_id"] = f"TWIN-{index // 2:02d}"
                item["pair_role"] = "benign" if is_indirect_benign else "high"
            if cohort == "benign_adversarial_controls":
                item["negative_control_for"] = ["ood", "toxicology", "end_organ"]
            oracle.append(item)
            provenance = {
                "without_jev_triage": expected,
                "with_jev_triage": expected,
                "ood_detected": cohort == "safety_floor_ood_conflicts",
                "ood_downgrade_revoked": cohort == "safety_floor_ood_conflicts",
                "tox_is_emergency": cohort == "unnamed_novel_toxidromes",
                "dual_crisis_active": cohort == "dual_medical_psychiatric_crisis",
                "dual_crisis_medical": cohort == "dual_medical_psychiatric_crisis",
                "dual_crisis_psych": cohort == "dual_medical_psychiatric_crisis",
                "dual_crisis_composition_valid": cohort == "dual_medical_psychiatric_crisis",
                "end_organ_findings": ["coupling"] if cohort == "end_organ_coupling" else [],
            }
            predictions.append({
                "case_id": case_id,
                "final_triage": expected,
                "advice": "Gọi 115 và đến khoa Cấp cứu ngay." if expected == "EMERGENCY" else "Đánh giá phù hợp.",
                "decision_source": "deterministic",
                "provenance": provenance,
            })

    report = evaluate_v10_records(predictions, oracle)
    assert report["dataset_contract_passed"] is True
    assert report["all_gates_passed"] is True
    assert report["overall_status"] == "PASSED"
    assert all(item["passed"] for item in report["cohort_contract"].values())
    assert report["jev_counterfactual"]["correct_to_wrong"] == 0
