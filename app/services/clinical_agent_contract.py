"""Structured clinical contract for the agent-first response path.

The deterministic stack owns facts, safety floors, red flags and tool results.
The contextual reasoning layer owns a diagnosis-neutral episode representation,
bounded mechanism hypotheses, and the single highest-information unanswered
question. The Writer still owns final patient-facing composition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.chat import ChatIntent
from app.services.clinical_episode_model import build_clinical_episode_model
from app.services.clinical_reasoning.context_integration import enrich_patient_context
from app.services.contextual_clinical_reasoner import build_contextual_reasoning_frame


@dataclass(frozen=True)
class ClinicalAgentContract:
    envelope: dict[str, Any]
    claims: list[dict[str, Any]]


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _safe_patient_context(context: dict[str, Any] | None) -> dict[str, Any]:
    source = context or {}
    # Patient identifiers and previous generated answer state must never become
    # medical evidence for the writer. V28.1 structured clinical evidence is
    # explicitly allowed because it is derived only from the current user text
    # plus bounded non-identifying safety context.
    allowed = (
        "age",
        "sex",
        "current_medications",
        "allergies",
        "conditions",
        "clinical_context",
        "clinical_context_meta",
    )
    return {key: source.get(key) for key in allowed if source.get(key) not in (None, [], "")}


def _questions(result: dict[str, Any]) -> list[str]:
    values = result.get("clarifying_questions") or result.get("guidance_questions") or []
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()][:3]


def _episode_messages(question: str) -> list[dict[str, str]]:
    """Recover user-turn boundaries from the active episode text passed by chat.

    The triage orchestrator already passes the active episode, not merely the
    latest sentence. It joins recent user turns with newlines and prefixes the
    latest turn with ``Lượt hiện tại:``. Keeping each line as a separate user
    turn lets V25 compute deltas without giving the Writer old generated prose.
    """
    lines = [line.strip() for line in question.splitlines() if line.strip()]
    if not lines:
        lines = [question.strip()]
    messages: list[dict[str, str]] = []
    for line in lines:
        if line.lower().startswith("lượt hiện tại:"):
            line = line.split(":", 1)[1].strip()
        if line:
            messages.append({"role": "user", "content": line})
    return messages or [{"role": "user", "content": question.strip()}]


def _contextual_reasoning(
    question: str,
    urgency: str,
    messages: Sequence[Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Build V25 context fail-softly; safety behavior never depends on it."""
    try:
        resolved_messages = messages or _episode_messages(question)
        episode = build_clinical_episode_model(
            episode_id="writer-active-episode",
            messages=resolved_messages,
        )
        # The semantic parser intentionally focuses on clinical findings. Keep
        # the already-resolved user-authored episode narrative as well so a
        # trigger such as prolonged screen exposure is not lost between turns.
        episode = episode.model_copy(
            update={
                "latest_user_message": question,
                "active_episode_text": question,
            }
        )
        reasoning = build_contextual_reasoning_frame(episode, urgency=urgency)
        return episode.to_agent_payload(), reasoning.to_agent_payload()
    except Exception:
        # The legacy safety contract remains authoritative if contextual
        # explanation construction cannot complete.
        return None, None


def build_clinical_agent_contract(
    *,
    intent: ChatIntent,
    question: str,
    clinical_result: dict[str, Any] | None,
    patient_context: dict[str, Any] | None = None,
) -> ClinicalAgentContract:
    result = dict(clinical_result or {})
    # V28.1 must be available before the contract is frozen. Previously the
    # enrichment happened later in AnswerAgentPipeline._execute(), which meant
    # Writer/Reviewer could receive the old contract without negation/context
    # evidence. Enriching here makes the structured evidence part of the
    # authoritative agent envelope while keeping deterministic urgency intact.
    enriched_context = enrich_patient_context(patient_context, question)
    claims: list[dict[str, Any]] = []

    def add(category: str, text: str, *, required: bool = True, locked: bool = False) -> None:
        value = text.strip()
        if not value:
            return
        claims.append(
            {
                "id": f"{category}_{len(claims) + 1}",
                "category": category,
                "text": value,
                "required": required,
                "locked": locked,
            }
        )

    urgency = _text(result.get("urgency") or result.get("escalation_level") or "ROUTINE").upper()
    episode_payload: dict[str, Any] | None = None
    reasoning_payload: dict[str, Any] | None = None

    if intent == "triage":
        conv_messages = enriched_context.get("conversation_messages") or (
            patient_context.get("conversation_messages") if isinstance(patient_context, dict) else None
        )
        episode_payload, reasoning_payload = _contextual_reasoning(
            question,
            urgency,
            messages=conv_messages,
        )
        add("summary", f"Mức xử trí tối thiểu đã được hệ thống an toàn xác định: {urgency}.")

        specialty = result.get("recommended_specialty")
        if isinstance(specialty, dict):
            label = _text(specialty.get("label"))
            if label:
                add("finding", f"Hướng chuyên khoa hiện tại: {label}.", required=False)

        red_flags = result.get("red_flags") or []
        if isinstance(red_flags, list):
            for flag in red_flags[:6]:
                add("finding", f"Dấu hiệu đã được xác nhận từ bệnh cảnh hiện tại: {_text(flag)}.")

        if reasoning_payload:
            for mechanism in reasoning_payload.get("mechanisms", [])[:4]:
                statement = _text(mechanism.get("patient_safe_statement"))
                explanation = _text(mechanism.get("mechanism"))
                if statement and explanation:
                    add(
                        "mechanism",
                        f"{statement} Cơ chế có thể giải thích: {explanation}",
                        required=False,
                    )

        if urgency == "EMERGENCY" or bool(result.get("emergency_flag")):
            # This is a safety constraint, not a response template. The writer
            # may explain around it but must preserve the immediate action.
            add(
                "action",
                "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe và không trì hoãn để tiếp tục hỏi trực tuyến.",
                locked=True,
            )
            add(
                "safety",
                "Không được hạ mức xử trí cấp cứu chỉ vì triệu chứng tạm thời giảm hoặc người bệnh muốn ở nhà theo dõi.",
                locked=False,
            )
        else:
            advice = _text(result.get("advice"))
            if advice:
                add("action", advice, required=False)

            next_question = _text((reasoning_payload or {}).get("next_best_question"))
            if next_question:
                add("question", next_question, required=False)
            else:
                for value in _questions(result):
                    add("question", value, required=False)

    elif intent == "safety":
        risk = _text(result.get("overall_risk") or result.get("risk_level") or result.get("severity"))
        if risk:
            add("summary", f"Mức nguy cơ an toàn thuốc hiện tại: {risk}.")
        for key in ("warnings", "alerts", "recommendations", "actions"):
            values = result.get(key) or []
            if isinstance(values, list):
                for value in values[:6]:
                    if isinstance(value, dict):
                        message = _text(value.get("message") or value.get("text") or value.get("recommendation"))
                    else:
                        message = _text(value)
                    if message:
                        add("safety", message, required=True, locked=False)

    # Hard medication contraindications become locked safety claims so the
    # Writer cannot silently omit them and the existing deterministic locked-
    # claim gate will reject a draft that changes/removes the prohibition.
    clinical_context = enriched_context.get("clinical_context")
    if isinstance(clinical_context, dict):
        medication_safety = clinical_context.get("medication_safety")
        if isinstance(medication_safety, dict) and medication_safety.get("allowed") is False:
            guidance = _text(medication_safety.get("guidance"))
            if guidance:
                add("safety", guidance, required=True, locked=True)

    envelope = {
        "version": "v25-contextual-reasoning",
        "intent": intent,
        "user_question": question,
        "clinical_result": result,
        "patient_context": _safe_patient_context(enriched_context),
        "clinical_episode": episode_payload,
        "reasoning_frame": reasoning_payload,
        "communication_contract": {
            "compose_original_response": True,
            "legacy_template_prose_is_not_evidence": True,
            "directly_answer_main_concern_first": True,
            "detect_and_correct_dangerous_misconceptions": True,
            "explain_mechanism_in_plain_language_only_when_supported": True,
            "separate_assessment_from_diagnosis": True,
            "give_concrete_next_action": True,
            "avoid_generic_non_answers": True,
            "question_budget": 0 if urgency == "EMERGENCY" else 1,
            "emergency_action_precedes_explanation": urgency == "EMERGENCY",
            "unknown_is_not_negative": True,
            "reason_from_episode_delta_not_only_latest_sentence": True,
            "preserve_historical_hard_risk_until_explicitly_invalidated": True,
            "use_reasoning_frame_next_question_when_present": True,
            "respect_v28_positive_negative_findings": True,
            "never_promote_negated_findings_to_present": True,
            "obey_medication_safety_context": True,
        },
        "professional_response_principles": [
            "Address the patient's actual concern before background explanation.",
            "Explain what in the story supports the working explanation and what remains unknown.",
            "Describe plausible symptom mechanisms in plain language without turning them into a diagnosis.",
            "Treat unmentioned findings as unknown, never as negative findings.",
            "Treat explicitly negated V28 findings as absent in the current turn; never reinterpret them as positive red flags.",
            "Use the V28 domain assessment as diagnosis-neutral context and never let it override a higher deterministic safety floor.",
            "Obey medication_safety.allowed=false as a hard prohibition against recommending the contraindicated action.",
            "Update the assessment from new facts instead of repeating the previous answer.",
            "If the patient proposes a dangerous action, interrupt and correct it before explaining why.",
            "Give a specific action plan and a clear threshold for seeking care.",
            "Ask only the single highest-information follow-up question when it can change management.",
            "Do not reuse fixed response templates or infer patient facts from rule antecedents.",
        ],
    }
    return ClinicalAgentContract(envelope=envelope, claims=claims)
