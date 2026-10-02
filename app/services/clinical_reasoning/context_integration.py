"""V28.1 clinical context integration helpers.

Keeps clinical evidence extraction separate from LLM generation. The adapter
adds structured context into the existing agent state without allowing agents
to override safety decisions.
"""

from __future__ import annotations

from typing import Any

from app.services.clinical_reasoning.context_router import ClinicalContextRouter
from app.services.clinical_reasoning.medication_safety import MedicationSafetyPipeline
from app.services.clinical_reasoning.quality_gate import ResponseQualityReviewer


_router = ClinicalContextRouter()
_medication_pipeline = MedicationSafetyPipeline()
_quality_reviewer = ResponseQualityReviewer()


def enrich_patient_context(
    patient_context: dict[str, Any] | None,
    question: str,
) -> dict[str, Any]:
    """Attach structured clinical observations and medication safety to the agent context."""
    context = dict(patient_context or {})
    result = _router.parse(question)
    med_safety = _medication_pipeline.evaluate(question, context)

    context["clinical_context"] = {
        "symptoms": result.symptoms,
        "triggers": result.triggers,
        "severity": result.severity,
        "positive_findings": result.positive_findings,
        "negative_findings": result.negative_findings,
        "hypothetical_findings": result.hypothetical_findings,
        "risk_features": result.risk_features,
        "is_hypothetical": result.is_hypothetical,
        "domain_assessment": (
            {
                "risk_level": result.domain_assessment.risk_level,
                "subtype": result.domain_assessment.subtype,
                "rationale": result.domain_assessment.rationale,
                "suggested_action": result.domain_assessment.suggested_action,
                "red_flags": result.domain_assessment.red_flags,
            }
            if result.domain_assessment
            else None
        ),
        "medication_safety": {
            "allowed": med_safety.allowed,
            "warning_notes": med_safety.warning_notes,
            "contraindications": med_safety.contraindications_detected,
            "guidance": med_safety.guidance,
        },
    }

    # Safety floor: this is evidence only, never an autonomous diagnosis.
    context["clinical_context_meta"] = {
        "source": "v28.1_clinical_context_router",
        "diagnosis_generated": False,
        "severity_override_allowed": False,
        "hypothetical_findings_are_not_current": True,
    }

    return context


def review_response_quality(
    question: str,
    response_text: str,
    domain: str | None = None,
) -> Any:
    """Run post-generation quality gate on agent response."""
    return _quality_reviewer.review(question, response_text, domain)
