"""V28.1 clinical context integration helpers.

Keeps clinical evidence extraction separate from LLM generation. The adapter
adds structured context into the existing agent state without allowing agents
to override safety decisions.
"""

from __future__ import annotations

from typing import Any

from app.services.clinical_reasoning.context_router import ClinicalContextRouter


_router = ClinicalContextRouter()


def enrich_patient_context(
    patient_context: dict[str, Any] | None,
    question: str,
) -> dict[str, Any]:
    """Attach structured clinical observations to the agent context."""
    context = dict(patient_context or {})
    result = _router.parse(question)

    context["clinical_context"] = {
        "symptoms": result.symptoms,
        "triggers": result.triggers,
        "severity": result.severity,
        "positive_findings": result.positive_findings,
        "negative_findings": result.negative_findings,
        "risk_features": result.risk_features,
    }

    # Safety floor: this is evidence only, never an autonomous diagnosis.
    context["clinical_context_meta"] = {
        "source": "v28.1_clinical_context_router",
        "diagnosis_generated": False,
        "severity_override_allowed": False,
    }

    return context
