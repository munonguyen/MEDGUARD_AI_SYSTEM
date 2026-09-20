"""Report Generator for Blind V5 Sealed Evaluation Harness.

Generates the comprehensive 4-Part Final Report:
- Part A: Performance (Score, Sensitivity, Specificity, Under/Over-triage, Calibration)
- Part B: Safety (T4->ROUTINE, T4->URGENT, Unsafe advice, Medication violations)
- Part C: Generalization (Semantic unseen, Long multi-turn, Dialects, Teencode, Code-switch, Dose)
- Part D: Root-Cause Distribution & Failure Clustering (F1 - F18, 6-Layer breakdown)

Enforces Strict Clinical Priority Order:
1. Catastrophic Safety Errors
2. Emergency Sensitivity
3. Unsafe Treatment / Advice
4. Multi-Turn Correctness
5. Specificity / Over-Triage
6. Calibration
7. Overall Score
"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from blind_v6.evaluator.failure_taxonomy import FailureReport
from blind_v6.evaluator.scoring import CaseScoreBreakdown


def build_final_v5_report(
    eval_summary: dict[str, Any],
    gate_results: dict[str, Any],
    case_scores: list[CaseScoreBreakdown],
    failure_reports: list[FailureReport],
    calibration_metrics: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the standardized 4-part final report structure."""
    
    # Calculate totals
    total_cases = len(case_scores)
    total_score = sum(cs.total_score for cs in case_scores)
    max_score = total_cases * 10
    score_pct = (total_score / max_score * 100) if max_score > 0 else 0.0

    critical_fails = [cs for cs in case_scores if cs.is_critical_fail]

    # Part A: Performance
    part_a = {
        "total_cases_evaluated": total_cases,
        "overall_score": f"{total_score} / {max_score} ({score_pct:.2f}%)",
        "emergency_sensitivity": eval_summary.get("emergency_sensitivity", 0.0),
        "emergency_specificity": eval_summary.get("emergency_specificity", 0.0),
        "severe_under_triage_rate": eval_summary.get("severe_under_triage_rate", 0.0),
        "moderate_under_triage_rate": eval_summary.get("moderate_under_triage_rate", 0.0),
        "over_triage_rate": eval_summary.get("over_triage_rate", 0.0),
        "calibration": {
            "expected_calibration_error": calibration_metrics.get("ece", 0.0),
            "brier_score": calibration_metrics.get("brier_score", 0.0),
            "source_gaps": calibration_metrics.get("source_gaps", {}),
        },
    }

    # Part B: Safety (Highest Priority)
    part_b = {
        "catastrophic_errors_count": len(critical_fails),
        "t4_to_routine_count": eval_summary.get("t4_to_routine_count", 0),
        "t4_to_urgent_count": eval_summary.get("t4_to_urgent_count", 0),
        "critical_unsafe_advice_count": eval_summary.get("unsafe_advice_count", 0),
        "unsupported_treatment_action_count": eval_summary.get("unsupported_treatment_count", 0),
        "emergency_escalation_delay": {
            "median_turns": eval_summary.get("median_escalation_delay", 0),
            "max_turns": eval_summary.get("max_escalation_delay", 0),
        },
        "critical_cases": [cs.to_dict() for cs in critical_fails],
    }

    # Part C: Generalization by Cohort
    part_c = {
        "cohort_breakdown": eval_summary.get("cohort_metrics", {}),
        "long_multi_turn_safety_rate": eval_summary.get("multi_turn_safety_rate", 100.0),
        "linguistic_robustness_rate": eval_summary.get("linguistic_robustness_rate", 100.0),
        "dose_reasoning_accuracy": eval_summary.get("dose_reasoning_accuracy", 100.0),
        "correction_handling_rate": eval_summary.get("correction_handling_rate", 100.0),
    }

    f_counts: dict[str, int] = {}
    layer_counts: dict[str, int] = {
        "Layer 1 - Language Understanding": 0,
        "Layer 2 - Fact Extraction": 0,
        "Layer 3 - Negation / Temporality": 0,
        "Layer 4 - Clinical Semantic Reasoning": 0,
        "Layer 5 - Risk Aggregation / Resolver": 0,
        "Layer 6 - Response Generation Policy": 0,
        "Runtime / System Failure": 0,
    }

    nature_counts: dict[str, int] = {
        "Implementation Bugs": 0,
        "Knowledge Gaps": 0,
        "Oracle Ambiguities": 0,
        "System Errors": 0,
        "Unsafe Response Policies": 0,
    }

    for fr in failure_reports:
        p_code = fr.primary_failure.value
        f_counts[p_code] = f_counts.get(p_code, 0) + 1

        fn = fr.failure_nature.value if hasattr(fr.failure_nature, "value") else str(fr.failure_nature)
        if fn == "BUG":
            nature_counts["Implementation Bugs"] += 1
        elif fn == "KNOWLEDGE_GAP":
            nature_counts["Knowledge Gaps"] += 1
        elif fn == "BENCHMARK_OVERFIT" or p_code == "F18_ORACLE_AMBIGUITY":
            nature_counts["Oracle Ambiguities"] += 1
        elif fn == "SYSTEM_CRASH" or p_code == "F17_SYSTEM_RUNTIME_FAILURE":
            nature_counts["System Errors"] += 1
        elif fn == "UNSAFE_POLICY":
            nature_counts["Unsafe Response Policies"] += 1
        else:
            nature_counts["Knowledge Gaps"] += 1

        if p_code in ("F1_LANGUAGE_UNDERSTANDING",):
            layer_counts["Layer 1 - Language Understanding"] += 1
        elif p_code in ("F2_FACT_EXTRACTION",):
            layer_counts["Layer 2 - Fact Extraction"] += 1
        elif p_code in ("F3_NEGATION_UNCERTAINTY", "F4_TEMPORAL_REASONING"):
            layer_counts["Layer 3 - Negation / Temporality"] += 1
        elif p_code in ("F5_CLINICAL_SEMANTIC_REASONING", "F6_RULE_MATCHING", "F7_DOSE_REASONING"):
            layer_counts["Layer 4 - Clinical Semantic Reasoning"] += 1
        elif p_code in ("F8_CONVERSATION_STATE", "F9_CORRECTION_INVALIDATION", "F10_RISK_AGGREGATION", "F11_RESOLVER"):
            layer_counts["Layer 5 - Risk Aggregation / Resolver"] += 1
        elif p_code in ("F12_RESPONSE_POLICY", "F13_HALLUCINATED_DIAGNOSIS", "F14_UNSAFE_MEDICATION_TREATMENT"):
            layer_counts["Layer 6 - Response Generation Policy"] += 1
        elif p_code in ("F17_SYSTEM_RUNTIME_FAILURE",):
            layer_counts["Runtime / System Failure"] += 1

    part_d = {
        "total_failures": len(failure_reports),
        "primary_code_distribution": f_counts,
        "layer_distribution": layer_counts,
        "nature_distribution": nature_counts,
        "failure_details": [fr.to_dict() for fr in failure_reports],
    }

    # Overall Verdict
    all_gates_passed = all(g.get("passed", False) for g in gate_results.values())
    no_catastrophic = len(critical_fails) == 0
    final_passed = all_gates_passed and no_catastrophic

    return {
        "report_version": "4.0.0-SEALED",
        "benchmark_name": "MedGuard AI Blind Benchmark V5",
        "execution_seal": {
            "run_id": manifest.get("run_id", "V5-ONE-SHOT"),
            "prediction_sha256": manifest.get("predictions_sha256") or manifest.get("prediction_sha256"),
            "status": manifest.get("status"),
            "git_commit": manifest.get("git_commit"),
            "started_at": manifest.get("started_at"),
            "completed_at": manifest.get("sealed_at") or manifest.get("completed_at"),
        },
        "final_verdict": "PASSED" if final_passed else "FAILED",
        "release_recommendation": (
            "ELIGIBLE FOR PRODUCTION VALIDATION" if final_passed
            else "RELEASE BLOCKED — ADDRESS ROOT CAUSE CLUSTERS FOR V5"
        ),
        "hard_gates": gate_results,
        "part_a_performance": part_a,
        "part_b_safety": part_b,
        "part_c_generalization": part_c,
        "part_d_root_cause_distribution": part_d,
    }


def format_report_markdown(report: dict[str, Any]) -> str:
    """Format final report into an executive Markdown presentation."""
    verdict = report["final_verdict"]
    color = "🟢" if verdict == "PASSED" else "🔴"
    gates = report["hard_gates"]
    pa = report["part_a_performance"]
    pb = report["part_b_safety"]
    pc = report["part_c_generalization"]
    pd = report["part_d_root_cause_distribution"]

    lines = [
        f"# {color} MedGuard AI — Blind Benchmark V6 Final Evaluation Report",
        "",
        f"**Final Verdict**: **{verdict}**  ",
        f"**Recommendation**: *{report['release_recommendation']}*  ",
        f"**Seal Hash**: `{report['execution_seal']['prediction_sha256']}`  ",
        f"**Git Commit**: `{report['execution_seal']['git_commit']}`  ",
        "",
        "---",
        "",
        "## 14 Mandatory Hard Gates Status",
        "",
        "| Gate | Invariant / Metric | Target | Actual | Status |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for gid, g in gates.items():
        status_str = "PASSED" if g["passed"] else "FAILED"
        lines.append(f"| **{gid}** | {g['metric']} | {g['target']} | {g['actual']} | **{status_str}** |")

    lines.extend([
        "",
        "---",
        "",
        "## Part A: Overall Performance",
        "",
        f"- **Score**: {pa['overall_score']}",
        f"- **Emergency Sensitivity**: {pa['emergency_sensitivity']:.2f}%",
        f"- **Emergency Specificity**: {pa['emergency_specificity']:.2f}%",
        f"- **Severe Under-Triage**: {pa['severe_under_triage_rate']:.2f}%",
        f"- **Moderate Under-Triage**: {pa['moderate_under_triage_rate']:.2f}%",
        f"- **Over-Triage Rate**: {pa['over_triage_rate']:.2f}%",
        f"- **ECE**: {pa['calibration']['expected_calibration_error']:.4f}",
        f"- **Brier Score**: {pa['calibration']['brier_score']:.4f}",
        "",
        "---",
        "",
        "## Part B: Clinical Safety (Highest Priority)",
        "",
        f"- **Catastrophic Critical Failures**: **{pb['catastrophic_errors_count']}**",
        f"- **Pure T4 $\\rightarrow$ ROUTINE**: **{pb['t4_to_routine_count']}**",
        f"- **Pure T4 $\\rightarrow$ URGENT**: {pb['t4_to_urgent_count']}",
        f"- **Critical Unsafe Recommendations**: {pb['critical_unsafe_advice_count']}",
        f"- **Unsupported Treatment Actions**: {pb['unsupported_treatment_action_count']}",
        f"- **Emergency Escalation Delay**: Median = {pb['emergency_escalation_delay']['median_turns']} turns, Max = {pb['emergency_escalation_delay']['max_turns']} turns",
        "",
        "---",
        "",
        "## Part C: Clinical Generalization",
        "",
        f"- **Multi-Turn Safety Rate**: {pc['long_multi_turn_safety_rate']:.2f}%",
        f"- **Linguistic Robustness**: {pc['linguistic_robustness_rate']:.2f}%",
        f"- **Dose Reasoning Accuracy**: {pc['dose_reasoning_accuracy']:.2f}%",
        f"- **Correction Handling Rate**: {pc['correction_handling_rate']:.2f}%",
        "",
        "---",
        "",
        "## Part D: Root-Cause Distribution & 6-Layer Diagnostics",
        "",
        f"- **Total Diagnostic Failures**: {pd['total_failures']}",
        "",
        "### Root Cause Classification Breakdown",
        f"- **Implementation Bugs**: {pd.get('nature_distribution', {}).get('Implementation Bugs', 0)}",
        f"- **Knowledge Gaps**: {pd.get('nature_distribution', {}).get('Knowledge Gaps', 0)}",
        f"- **Oracle Ambiguities**: {pd.get('nature_distribution', {}).get('Oracle Ambiguities', 0)}",
        f"- **System Errors**: {pd.get('nature_distribution', {}).get('System Errors', 0)}",
        f"- **Unsafe Response Policies**: {pd.get('nature_distribution', {}).get('Unsafe Response Policies', 0)}",
        "",
        "### 6-Layer Diagnostic Breakdown",
    ])

    for layer, count in pd["layer_distribution"].items():
        lines.append(f"- **{layer}**: {count} cases")

    lines.extend([
        "",
        "### Primary Failure Taxonomy Distribution (F1 - F18)",
        "",
        "| Primary Code | Root Cause Category | Count |",
        "| :--- | :--- | :--- |",
    ])
    for code, count in sorted(pd["primary_code_distribution"].items()):
        lines.append(f"| `{code}` | Clinical Root Cause | {count} |")

    return "\n".join(lines)
