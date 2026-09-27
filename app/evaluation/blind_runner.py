"""Multi-Dimensional Clinical Evaluation Runner.

Evaluates test cohorts against multi-dimensional clinical invariants:
1. Minimum Triage Safety (zero under-triage tolerance).
2. Must-include concepts and required red-flag warnings.
3. Must-not-include prohibitions (unsupported diagnoses, over-claiming certainty).
4. Medication safety invariants (forbidden drugs, contraindications).
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.evaluation.corpus_loader import ClinicalTestCase
from app.services.phase3_pipeline import Phase3ClinicalPipeline

URGENCY_RANK = {"ROUTINE": 1, "URGENT": 2, "EMERGENCY": 3}


class CaseEvaluationReport(BaseModel):
    case_id: str
    cohort: str
    passed: bool
    observed_triage: str
    expected_minimum_triage: str
    missing_must_includes: list[str] = Field(default_factory=list)
    found_must_not_includes: list[str] = Field(default_factory=list)
    found_forbidden_meds: list[str] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)


class CohortEvaluationSummary(BaseModel):
    total_evaluated: int = 0
    total_passed: int = 0
    pass_rate: float = 0.0
    emergency_recall: float = 0.0
    benign_specificity: float = 0.0
    unsupported_diagnosis_rate: float = 0.0
    reports: list[CaseEvaluationReport] = Field(default_factory=list)


class BlindEvaluationRunner:
    """Executes multi-dimensional clinical evaluations across test cohorts."""

    @classmethod
    def run_cohort(cls, cases: list[ClinicalTestCase]) -> CohortEvaluationSummary:
        reports: list[CaseEvaluationReport] = []
        emergency_cases = 0
        emergency_hits = 0
        benign_cases = 0
        benign_hits = 0
        unsupported_diag_cases = 0

        for case in cases:
            res = Phase3ClinicalPipeline.execute(query=case.input_text)
            final_ans = res.final_synthesis.final_answer.lower()
            observed_urgency = res.final_synthesis.urgency

            passed = True
            reasons: list[str] = []

            # 1. Minimum Triage Invariant (Strict monotonic safety)
            obs_rank = URGENCY_RANK.get(observed_urgency, 1)
            exp_rank = URGENCY_RANK.get(case.expected.minimum_triage, 1)

            if obs_rank < exp_rank:
                passed = False
                reasons.append(f"Under-triage detected: expected minimum {case.expected.minimum_triage}, observed {observed_urgency}")

            # Tracking Recall & Specificity
            if case.expected.minimum_triage == "EMERGENCY":
                emergency_cases += 1
                if observed_urgency == "EMERGENCY":
                    emergency_hits += 1

            if case.expected.minimum_triage == "ROUTINE":
                benign_cases += 1
                if observed_urgency == "ROUTINE":
                    benign_hits += 1

            # 2. Must-include checks
            missing_inc: list[str] = []
            for inc in case.expected.must_include:
                if inc.lower() not in final_ans:
                    # Allow slight morphological variants or safety notes
                    if not any(inc.lower() in rf.lower() for rf in res.final_synthesis.red_flags):
                        missing_inc.append(inc)

            if missing_inc:
                passed = False
                reasons.append(f"Missing required clinical concepts: {missing_inc}")

            # 3. Must-not-include checks (Prohibitions against unsupported diagnosis)
            found_prohib: list[str] = []
            for prohib in case.expected.must_not_include:
                if prohib.lower() in final_ans:
                    found_prohib.append(prohib)

            if found_prohib:
                passed = False
                unsupported_diag_cases += 1
                reasons.append(f"Forbidden phrase found: {found_prohib}")

            # 4. Forbidden medications
            found_meds: list[str] = []
            for med in case.expected.forbidden_medications:
                if med.lower() in final_ans and "không" not in final_ans:
                    found_meds.append(med)

            if found_meds:
                passed = False
                reasons.append(f"Forbidden medication suggested: {found_meds}")

            reports.append(
                CaseEvaluationReport(
                    case_id=case.case_id,
                    cohort=case.cohort,
                    passed=passed,
                    observed_triage=observed_urgency,
                    expected_minimum_triage=case.expected.minimum_triage,
                    missing_must_includes=missing_inc,
                    found_must_not_includes=found_prohib,
                    found_forbidden_meds=found_meds,
                    failure_reasons=reasons,
                )
            )

        total = len(cases)
        passed_count = sum(1 for r in reports if r.passed)

        return CohortEvaluationSummary(
            total_evaluated=total,
            total_passed=passed_count,
            pass_rate=round(passed_count / total, 4) if total > 0 else 0.0,
            emergency_recall=round(emergency_hits / emergency_cases, 4) if emergency_cases > 0 else 1.0,
            benign_specificity=round(benign_hits / benign_cases, 4) if benign_cases > 0 else 1.0,
            unsupported_diagnosis_rate=round(unsupported_diag_cases / total, 4) if total > 0 else 0.0,
            reports=reports,
        )
