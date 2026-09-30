from __future__ import annotations

from typing import Any

from app.services.clinical_agent_contract import ClinicalAgentContract
from app.services.response_policy.engine import build_response_policy


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _leading_mechanism(reasoning: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(reasoning, dict):
        return None
    mechanisms = reasoning.get("mechanisms") or []
    values = [item for item in mechanisms if isinstance(item, dict)]
    for item in values:
        if _text(item.get("role")) == "leading":
            return item
    return values[0] if values else None


def _explanation_frame(envelope: dict[str, Any]) -> dict[str, Any]:
    reasoning = envelope.get("reasoning_frame")
    episode = envelope.get("clinical_episode")
    leading = _leading_mechanism(reasoning if isinstance(reasoning, dict) else None)
    if not leading:
        return {
            "what_it_may_mean": None,
            "why": [],
            "mechanism": None,
            "what_would_change_the_assessment": [],
            "uncertainty": None,
            "next_best_question": (
                reasoning.get("next_best_question") if isinstance(reasoning, dict) else None
            ),
        }

    unknowns = []
    if isinstance(episode, dict):
        unknowns = episode.get("unknown_decision_relevant") or []
    change_triggers: list[str] = []
    for item in unknowns:
        if not isinstance(item, dict):
            continue
        question = _text(item.get("question"))
        if question:
            change_triggers.append(question)

    reasoning_limits = []
    if isinstance(reasoning, dict):
        reasoning_limits = [
            _text(value)
            for value in (reasoning.get("reasoning_limits") or [])
            if _text(value)
        ]

    evidence_for = leading.get("evidence_for") or []
    return {
        "what_it_may_mean": _text(leading.get("patient_safe_statement")) or _text(leading.get("label")) or None,
        "why": [_text(value) for value in evidence_for if _text(value)][:4],
        "mechanism": _text(leading.get("mechanism")) or None,
        "what_would_change_the_assessment": change_triggers[:4],
        "uncertainty": reasoning_limits[0] if reasoning_limits else None,
        "next_best_question": (
            reasoning.get("next_best_question") if isinstance(reasoning, dict) else None
        ),
    }


def apply_response_policy(contract: ClinicalAgentContract) -> ClinicalAgentContract:
    """Attach V27.1 communication policy without changing Safety Kernel facts.

    This adapter deliberately treats urgency as a safety constraint, not as
    patient-facing prose. It can strengthen composition requirements but cannot
    lower the deterministic urgency floor or invent clinical evidence.
    """
    envelope = dict(contract.envelope)
    result = envelope.get("clinical_result")
    result = result if isinstance(result, dict) else {}
    reasoning = envelope.get("reasoning_frame")
    reasoning = reasoning if isinstance(reasoning, dict) else None
    urgency = _text(result.get("urgency") or result.get("escalation_level") or "ROUTINE").upper()
    assessment_state = _text(envelope.get("assessment_state") or "UNDERSTOOD").upper()

    policy = build_response_policy(
        intent=_text(envelope.get("intent")),
        question=_text(envelope.get("user_question")),
        urgency=urgency,
        assessment_state=assessment_state,
        result=result,
        reasoning_payload=reasoning,
    )

    communication = dict(envelope.get("communication_contract") or {})
    communication.update(policy.to_payload())
    communication["generic_triage_summary_is_not_patient_explanation"] = True
    communication["require_because_therefore_explanation_when_supported"] = policy.explanation_required
    communication["reassurance_must_be_evidence_bounded"] = True
    communication["emergency_action_precedes_explanation"] = policy.action_first
    envelope["communication_contract"] = communication
    envelope["response_policy"] = policy.to_payload()
    envelope["explanation_frame"] = _explanation_frame(envelope)
    envelope["safety_constraints"] = {
        "urgency_floor": urgency,
        "cannot_be_lowered_by_writer": True,
        "emergency_action_first": policy.action_first,
    }

    updated_claims: list[dict[str, Any]] = []
    for raw in contract.claims:
        claim = dict(raw)
        category = _text(claim.get("category"))
        text = _text(claim.get("text"))

        # Technical routing labels are control-plane data, not useful patient
        # explanations. Keep the urgency in safety_constraints instead.
        if category == "summary" and text.startswith("Mức xử trí tối thiểu đã được hệ thống an toàn xác định:"):
            continue

        if category == "mechanism" and policy.mechanism_required:
            claim["required"] = True

        updated_claims.append(claim)

    return ClinicalAgentContract(envelope=envelope, claims=updated_claims)
