"""Build the bounded clinical contract consumed by MedGuard Writer/Reviewer.

The deterministic stack owns facts, safety floors, red flags and tool results.
The contextual reasoning layer owns a diagnosis-neutral episode representation,
bounded mechanism hypotheses, and the single highest-information unanswered
question. V27.1 adds a response-policy layer that controls communication depth,
evidence-bounded reassurance and proportionality before the Writer composes the
single patient-facing response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.chat import ChatIntent
from app.services.clinical_episode_model import build_clinical_episode_model
from app.services.clinical_text import normalize_search_text
from app.services.contextual_clinical_reasoner import build_contextual_reasoning_frame
from app.services.response_policy.engine import build_response_policy


@dataclass(frozen=True)
class ClinicalAgentContract:
    envelope: dict[str, Any]
    claims: list[dict[str, Any]]


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _safe_patient_context(patient_context: dict[str, Any] | None) -> dict[str, Any]:
    context = dict(patient_context or {})
    for key in (
        "patient_ref",
        "patient_id",
        "name",
        "full_name",
        "email",
        "phone",
        "address",
        "last_result",
    ):
        context.pop(key, None)
    return context


def _questions(result: dict[str, Any]) -> list[str]:
    raw = result.get("clarifying_questions") or result.get("questions") or []
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        value = _text(item)
        if value and value not in values:
            values.append(value)
    return values


def _episode_messages(question: str) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for raw in question.splitlines():
        text = raw.strip()
        if not text:
            continue
        if text.lower().startswith("lượt hiện tại:"):
            text = text.split(":", 1)[1].strip()
        if text:
            values.append({"role": "user", "content": text})
    if not values and question.strip():
        values.append({"role": "user", "content": question.strip()})
    return values


def _peripheral_joint_signal(question: str) -> bool:
    norm = normalize_search_text(question)
    joint_terms = (
        "khop tay",
        "khop ngon",
        "khop ngon tay",
        "khop co tay",
        "khop goi",
        "khop co chan",
        "nhieu khop",
        "cac khop",
        "dau khop",
        "sung khop",
        "cung khop",
    )
    return any(term in norm for term in joint_terms)


def _peripheral_joint_context(question: str) -> tuple[dict[str, Any], dict[str, Any]]:
    episode = {
        "version": "v27-peripheral-joint",
        "active_episode": question,
        "body_domain": "peripheral_joint",
        "known": [
            {
                "fact": "peripheral_joint_symptom",
                "evidence": question,
            }
        ],
        "unknown_decision_relevant": [
            {
                "fact": "joint_inflammatory_features",
                "question": "Các khớp có sưng, nóng, đỏ hoặc cứng khớp buổi sáng kéo dài không?",
                "impact": "high",
                "changes": ["inflammatory_vs_mechanical", "urgency"],
            },
            {
                "fact": "systemic_features",
                "question": "Bạn có sốt, rét run hoặc cảm giác mệt lả bất thường không?",
                "impact": "high",
                "changes": ["infection_risk", "urgency"],
            },
            {
                "fact": "trauma_or_overuse",
                "question": "Đau xuất hiện sau chấn thương, tập luyện hoặc vận động lặp lại không?",
                "impact": "medium",
                "changes": ["mechanical_explanation"],
            },
            {
                "fact": "neurovascular_deficit",
                "question": "Bạn có tê, yếu bàn tay hoặc ngón tay đổi màu/lạnh bất thường không?",
                "impact": "high",
                "changes": ["neurovascular_urgency"],
            },
        ],
    }
    reasoning = {
        "version": "v27-peripheral-joint",
        "mechanisms": [
            {
                "hypothesis_id": "peripheral_joint_nonspecific",
                "label": "Đau khớp ngoại vi chưa xác định nguyên nhân",
                "role": "leading",
                "confidence": "uncertain",
                "mechanism": (
                    "Đau ở các khớp tay có thể đến từ mô quanh khớp, quá tải cơ học hoặc viêm; "
                    "cần thêm dấu hiệu tại khớp và triệu chứng toàn thân để phân biệt."
                ),
                "patient_safe_statement": (
                    "Đau ở các khớp tay có nhiều nhóm nguyên nhân khác nhau và hiện chưa đủ dữ kiện để chọn một nguyên nhân cụ thể."
                ),
                "evidence_for": [question],
                "evidence_against": [],
            }
        ],
        "reasoning_limits": [
            "Chưa có thông tin về sưng/nóng/đỏ, cứng khớp buổi sáng, sốt, chấn thương hoặc triệu chứng thần kinh-mạch máu."
        ],
        "next_best_question": "Các khớp có sưng, nóng, đỏ hoặc cứng khớp buổi sáng kéo dài không?",
    }
    return episode, reasoning


def _contextual_reasoning(question: str, urgency: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if _peripheral_joint_signal(question):
        return _peripheral_joint_context(question)
    episode = build_clinical_episode_model(_episode_messages(question))
    reasoning = build_contextual_reasoning_frame(episode, urgency=urgency)
    return episode.to_payload(), reasoning.to_payload()


def _assessment_state(result: dict[str, Any], urgency: str) -> str:
    if urgency == "EMERGENCY" or bool(result.get("emergency_flag")):
        return "SAFETY_ESCALATED"
    if urgency in {"UNRESOLVED", "UNKNOWN", "UNCERTAIN", ""}:
        return "INSUFFICIENT_CONTEXT"
    matched = result.get("matched")
    confidence = result.get("confidence")
    if matched is False:
        return "INSUFFICIENT_CONTEXT"
    try:
        confidence_value = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_value = None
    if confidence_value is not None and confidence_value <= 0:
        return "INSUFFICIENT_CONTEXT"
    if confidence_value is not None and confidence_value < 0.70:
        return "PARTIALLY_UNDERSTOOD"
    return "UNDERSTOOD"


def _leading_mechanism(reasoning_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(reasoning_payload, dict):
        return None
    mechanisms = reasoning_payload.get("mechanisms") or []
    values = [item for item in mechanisms if isinstance(item, dict)]
    for item in values:
        if _text(item.get("role")) == "leading":
            return item
    return values[0] if values else None


def _explanation_frame(
    episode_payload: dict[str, Any] | None,
    reasoning_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    leading = _leading_mechanism(reasoning_payload)
    if not leading:
        return {
            "what_it_may_mean": None,
            "why": [],
            "mechanism": None,
            "what_would_change_the_assessment": [],
            "uncertainty": None,
            "next_best_question": _text((reasoning_payload or {}).get("next_best_question")) or None,
        }

    change_triggers: list[str] = []
    if isinstance(episode_payload, dict):
        for item in episode_payload.get("unknown_decision_relevant") or []:
            if not isinstance(item, dict):
                continue
            question = _text(item.get("question"))
            if question:
                change_triggers.append(question)

    limits = [
        _text(value)
        for value in (reasoning_payload or {}).get("reasoning_limits", [])
        if _text(value)
    ]
    evidence_for = leading.get("evidence_for") or []
    return {
        "what_it_may_mean": _text(leading.get("patient_safe_statement")) or _text(leading.get("label")) or None,
        "why": [_text(value) for value in evidence_for if _text(value)][:4],
        "mechanism": _text(leading.get("mechanism")) or None,
        "what_would_change_the_assessment": change_triggers[:4],
        "uncertainty": limits[0] if limits else None,
        "next_best_question": _text((reasoning_payload or {}).get("next_best_question")) or None,
    }


def build_clinical_agent_contract(
    *,
    intent: ChatIntent,
    question: str,
    clinical_result: dict[str, Any] | None,
    patient_context: dict[str, Any] | None = None,
) -> ClinicalAgentContract:
    result = dict(clinical_result or {})
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
    assessment_state = _assessment_state(result, urgency)
    episode_payload: dict[str, Any] | None = None
    reasoning_payload: dict[str, Any] | None = None

    if intent == "triage":
        episode_payload, reasoning_payload = _contextual_reasoning(question, urgency)

    response_policy = build_response_policy(
        intent=intent,
        question=question,
        urgency=urgency,
        assessment_state=assessment_state,
        result=result,
        reasoning_payload=reasoning_payload,
    )

    if intent == "triage" and assessment_state == "INSUFFICIENT_CONTEXT":
        add(
            "summary",
            "Hiện chưa có đủ dữ kiện để hiểu rõ bệnh cảnh hoặc đưa ra nhận định lâm sàng chắc chắn.",
        )
    elif intent == "triage" and assessment_state == "PARTIALLY_UNDERSTOOD":
        add(
            "summary",
            "Hiện bệnh cảnh mới được hiểu một phần; cần giữ rõ giới hạn dữ kiện trước khi đưa ra nhận định chắc hơn.",
        )

    if intent == "triage":
        specialty = result.get("recommended_specialty")
        if isinstance(specialty, dict) and assessment_state not in {"INSUFFICIENT_CONTEXT"}:
            label = _text(specialty.get("label"))
            if label:
                add("finding", f"Hướng chuyên khoa hiện tại: {label}.", required=False)

        red_flags = result.get("red_flags") or []
        if isinstance(red_flags, list):
            for flag in red_flags[:6]:
                text = _text(flag)
                if text:
                    add("finding", f"Dấu hiệu đã được xác nhận từ bệnh cảnh hiện tại: {text}.")

        if reasoning_payload:
            for mechanism in reasoning_payload.get("mechanisms", [])[:4]:
                if not isinstance(mechanism, dict):
                    continue
                statement = _text(mechanism.get("patient_safe_statement"))
                explanation = _text(mechanism.get("mechanism"))
                if statement and explanation:
                    add(
                        "mechanism",
                        f"{statement} Cơ chế có thể giải thích: {explanation}",
                        required=response_policy.mechanism_required,
                    )

        if urgency == "EMERGENCY" or bool(result.get("emergency_flag")):
            add(
                "action",
                "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe và không trì hoãn để tiếp tục hỏi trực tuyến.",
                locked=True,
            )
            add(
                "safety",
                "Không được hạ mức xử trí cấp cứu chỉ vì triệu chứng tạm thời giảm hoặc vì người bệnh muốn trì hoãn việc được đánh giá trực tiếp.",
                locked=False,
            )
        else:
            if assessment_state == "UNDERSTOOD":
                advice = _text(result.get("advice"))
                if advice:
                    add("action", advice, required=False)

            next_question = _text((reasoning_payload or {}).get("next_best_question"))
            question_required = assessment_state in {"INSUFFICIENT_CONTEXT", "PARTIALLY_UNDERSTOOD"}
            if next_question and response_policy.question_budget > 0:
                add("question", next_question, required=question_required)
            elif response_policy.question_budget > 0:
                for value in _questions(result)[: response_policy.question_budget]:
                    add("question", value, required=question_required)

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

    policy_payload = response_policy.to_payload()
    envelope = {
        "version": "v27-semantic-authority",
        "response_policy_version": "v27.1-adaptive-response-policy",
        "intent": intent,
        "user_question": question,
        "clinical_result": result,
        "assessment_state": assessment_state,
        "patient_context": _safe_patient_context(patient_context),
        "clinical_episode": episode_payload,
        "reasoning_frame": reasoning_payload,
        "response_policy": policy_payload,
        "explanation_frame": _explanation_frame(episode_payload, reasoning_payload),
        "safety_constraints": {
            "urgency_floor": urgency,
            "cannot_be_lowered_by_writer": True,
            "emergency_action_first": response_policy.action_first,
        },
        "communication_contract": {
            "compose_original_response": True,
            "legacy_template_prose_is_not_evidence": True,
            "directly_answer_main_concern_first": True,
            "detect_and_correct_dangerous_misconceptions": True,
            "explain_mechanism_in_plain_language_only_when_supported": True,
            "separate_assessment_from_diagnosis": True,
            "separate_epistemic_state_from_urgency": True,
            "never_present_unresolved_as_routine_fact": True,
            "give_concrete_next_action": True,
            "avoid_generic_non_answers": True,
            "generic_triage_summary_is_not_patient_explanation": True,
            "require_because_therefore_explanation_when_supported": response_policy.explanation_required,
            "reassurance_must_be_evidence_bounded": True,
            "communication_goal": response_policy.communication_goal.value,
            "response_depth": response_policy.response_depth.value,
            "required_sections": list(response_policy.required_sections),
            "mechanism_required": response_policy.mechanism_required,
            "reassurance": response_policy.reassurance.to_payload(),
            "target_length": response_policy.target_length.to_payload(),
            "question_budget": response_policy.question_budget,
            "emergency_action_precedes_explanation": response_policy.action_first,
            "unknown_is_not_negative": True,
            "reason_from_episode_delta_not_only_latest_sentence": True,
            "preserve_historical_hard_risk_until_explicitly_invalidated": True,
            "use_reasoning_frame_next_question_when_present": True,
            "response_must_remain_relevant_to_active_episode": True,
        },
        "professional_response_principles": [
            "Address the patient's actual concern before background explanation.",
            "Explain what in the story supports the working explanation and what remains unknown.",
            "Describe plausible symptom mechanisms in plain language without turning them into a diagnosis.",
            "Use reassurance only when response_policy.reassurance.allowed is true and explicitly state its limitations.",
            "Match response length and explanation depth to response_policy instead of using a one-size-fits-all answer.",
            "Treat unmentioned findings as unknown, never as negative findings.",
            "Do not convert an unresolved semantic match into a reassuring ROUTINE conclusion.",
            "Update the assessment from new facts instead of repeating the previous answer.",
            "If the patient proposes a dangerous action, interrupt and correct it before explaining why.",
            "Give a specific action plan and a clear threshold for seeking care.",
            "Ask only the allowed number of high-information follow-up questions.",
            "Do not reuse fixed response templates or infer patient facts from rule antecedents.",
        ],
    }
    return ClinicalAgentContract(envelope=envelope, claims=claims)
