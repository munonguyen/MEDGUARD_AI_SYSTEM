from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any
from urllib import request as urllib_request

from app.models.adaptive_routing import KevDecisionSignal, SeverityChoice


_ACUITY_CRITERIA: dict[str, str] = {
    "ROUTINE": "Stable low-acuity presentation appropriate for self-care, monitoring, or routine follow-up when no higher safety floor applies.",
    "URGENT": "Needs prompt clinical evaluation, usually same day or soon, but no current hard emergency feature is established.",
    "EMERGENCY": "Potential immediate threat to airway, breathing, circulation, neurologic function, severe toxicity, or another time-critical condition.",
    "UNKNOWN": "The state is incomplete, ambiguous, contradictory, or too uncertain for a safe routing choice.",
    "OUT_OF_SCOPE": "The request is not a patient-health severity decision.",
}

_SEVERITY_LEVELS = [
    "minimal clinical concern",
    "mild stable concern",
    "moderate concern needing closer assessment",
    "high concern needing prompt evaluation",
    "critical time-sensitive concern",
]


def _entropy(probabilities: dict[str, float]) -> float:
    values = [max(0.0, float(value)) for value in probabilities.values()]
    total = sum(values)
    if total <= 0:
        return 0.0
    normalized = [value / total for value in values if value > 0]
    return -sum(value * math.log(value, 2) for value in normalized)


def _clinical_fallback(clinical_result: dict[str, Any]) -> KevDecisionSignal:
    urgency = str(clinical_result.get("urgency") or "UNKNOWN").upper()
    choice = SeverityChoice(urgency) if urgency in {"ROUTINE", "URGENT", "EMERGENCY"} else SeverityChoice.UNKNOWN
    probabilities = {name: 0.0 for name in SeverityChoice.__members__}
    probabilities[choice.value] = 1.0
    score = {
        SeverityChoice.ROUTINE: 0.8,
        SeverityChoice.URGENT: 2.7,
        SeverityChoice.EMERGENCY: 4.0,
        SeverityChoice.UNKNOWN: 2.0,
        SeverityChoice.OUT_OF_SCOPE: 0.0,
    }[choice]
    return KevDecisionSignal(
        choice=choice,
        probabilities=probabilities,
        severity_score=score,
        choice_confidence=1.0,
        score_confidence=1.0,
        entropy=0.0,
        source="clinical_fallback",
    )


@dataclass(frozen=True)
class KevRouterConfig:
    base_url: str | None = None
    model: str = "kev-latest"
    timeout_seconds: float = 0.35
    mode: str = "shadow"  # disabled | shadow | enforced


class KevRouter:
    """Thin decision-only adapter.

    Kev is advisory even in ``enforced`` mode: enforced means the resolver may
    use Kev uncertainty/disagreement to choose an UNCERTAIN/deeper path. It does
    not mean Kev may overwrite the validated clinical disposition.
    """

    def __init__(self, config: KevRouterConfig) -> None:
        self.config = config

    @property
    def enabled(self) -> bool:
        return bool(self.config.base_url) and self.config.mode in {"shadow", "enforced"}

    def evaluate(self, state: dict[str, Any], clinical_result: dict[str, Any]) -> KevDecisionSignal:
        if not self.enabled:
            return _clinical_fallback(clinical_result)

        body = {
            "state": state,
            "model": self.config.model,
            "questions": {
                "acuity": {
                    "type": "choice",
                    "instructions": "Choose the safest routing acuity for this structured state. Do not diagnose.",
                    "criteria": _ACUITY_CRITERIA,
                },
                "severity": {
                    "type": "score",
                    "instructions": "Rate routing severity on this ordered operations scale. This is not disease probability.",
                    "criteria": _SEVERITY_LEVELS,
                },
            },
        }
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib_request.Request(
            f"{self.config.base_url.rstrip('/')}/v1/systemone",
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            answers = payload.get("answers") or {}
            acuity = answers.get("acuity") or {}
            severity = answers.get("severity") or {}
            raw_choice = str(acuity.get("choice") or "UNKNOWN").upper()
            choice = SeverityChoice(raw_choice) if raw_choice in SeverityChoice.__members__ else SeverityChoice.UNKNOWN
            probabilities = {
                str(key).upper(): float(value)
                for key, value in (acuity.get("probabilities") or {}).items()
            }
            return KevDecisionSignal(
                choice=choice,
                probabilities=probabilities,
                severity_score=float(severity["score"]) if severity.get("score") is not None else None,
                choice_confidence=float(acuity.get("confidence") or 0.0),
                score_confidence=float(severity.get("confidence") or 0.0),
                entropy=_entropy(probabilities),
                source="kev",
            )
        except Exception:
            # Availability failures fall back to the already-resolved clinical
            # state. Kev must never make the response path unavailable.
            return _clinical_fallback(clinical_result)


def build_compact_kev_state(
    *,
    clinical_task: str,
    clinical_result: dict[str, Any],
    patient_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a compact, PHI-minimized state for decision-only inference."""
    context = patient_context or {}
    trace = clinical_result.get("trace") if isinstance(clinical_result.get("trace"), dict) else {}
    details = trace.get("details") if isinstance(trace, dict) else {}
    age = context.get("age")
    return {
        "clinical_task": clinical_task,
        "current_urgency": clinical_result.get("urgency"),
        "emergency_flag": bool(clinical_result.get("emergency_flag")),
        "red_flags": list(clinical_result.get("red_flags") or [])[:8],
        "reasons": list(clinical_result.get("reasons") or [])[:8],
        "specialty": clinical_result.get("recommended_specialty") or clinical_result.get("specialty"),
        "fact_coverage": float((details or {}).get("fact_coverage", 1.0) or 1.0),
        "age_band": (
            "child" if isinstance(age, int) and age < 18
            else "older_adult" if isinstance(age, int) and age >= 65
            else "adult_or_unknown"
        ),
        "has_medications": bool(context.get("current_medications")),
        "has_allergies": bool(context.get("allergies")),
    }
