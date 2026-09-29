"""Structured clinical contract for the agent-first response path.

The deterministic stack owns facts, safety floors, red flags and tool results.
The contextual reasoning layer owns a diagnosis-neutral episode representation,
bounded mechanism hypotheses, and the single highest-information unanswered
question. The Writer still owns final patient-facing composition.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.models.chat import ChatIntent
from app.services.clinical_episode_model import build_clinical_episode_model
from app.services.clinical_text import normalize_search_text
from app.services.contextual_clinical_reasoner import build_contextual_reasoning_frame


@dataclass(frozen=True)
class ClinicalAgentContract:
    envelope: dict[str, Any]
    claims: list[dict[str, Any]]


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _safe_patient_context(context: dict[str, Any] | None) -> dict[str, Any]:
    source = context or {}
    allowed = ("age", "sex", "current_medications", "allergies", "conditions")
    return {key: source.get(key) for key in allowed if source.get(key) not in (None, [], "")}


def _questions(result: dict[str, Any]) -> list[str]:
    values = result.get("clarifying_questions") or result.get("guidance_questions") or []
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()][:3]


def _episode_messages(question: str) -> list[dict[str, str]]:
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


def _peripheral_joint_signal(question: str) -> bool:
    """Detect specific peripheral-joint language independent of word order."""
    norm = normalize_search_text(question)
    joint_site = bool(
        re.search(
            r"\b(?:cac\s+|nhieu\s+)?khop\s+(?:ngon\s+tay|co\s+tay|ban\s+tay|tay)\b",
            norm,
        )
    )
    symptom = bool(
        re.search(
            r"\b(?:dau|nhuc|sung|nong|do|cung|han che cu dong|kho cu dong|kho nam|kho cam)\b",
            norm,
        )
    )
    return joint_site and symptom


def _peripheral_joint_context(
    question: str,
    episode_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Build a diagnosis-neutral hand/peripheral-joint reasoning envelope."""
    norm = normalize_search_text(question)
    unknowns: list[dict[str, Any]] = []

    def unknown(key: str, question_text: str, impact: str, changes: tuple[str, ...], rationale: str) -> None:
        unknowns.append(
            {
                "key": key,
                "question": question_text,
                "impact": impact,
                "changes": list(changes),
                "rationale": rationale,
            }
        )

    inflammatory_known = any(
        marker in norm
        for marker in (
            "sung",
            "nong",
            "do khop",
            "khop do",
            "khong sung",
            "khong nong",
            "khong do",
            "cung khop",
            "cung buoi sang",
        )
    )
    if not inflammatory_known:
        unknown(
            "joint_inflammation_pattern",
            "Các khớp có bị sưng/nóng/đỏ hoặc cứng rõ vào buổi sáng không?",
            "high",
            ("inflammatory_pathway", "urgency", "evaluation_priority"),
            "Sưng nóng đỏ hoặc cứng khớp buổi sáng giúp phân biệt quá tải cơ học với một quá trình viêm quanh/ở khớp và có thể thay đổi mức đánh giá.",
        )

    if not any(marker in norm for marker in ("sot", "khong sot", "lanh run", "khong lanh run")):
        unknown(
            "fever_systemic_features",
            "Bạn có sốt hoặc rét run kèm khớp sưng đau tăng nhanh không?",
            "critical",
            ("urgent_infection_evaluation",),
            "Sốt kèm một khớp sưng nóng đau tăng nhanh là dữ kiện an toàn quan trọng và có thể cần đánh giá sớm.",
        )

    if not any(
        marker in norm
        for marker in (
            "chan thuong",
            "nga",
            "va dap",
            "mang vac",
            "lap lai",
            "go phim",
            "tap gym",
            "khong chan thuong",
        )
    ):
        unknown(
            "trauma_or_repetitive_load",
            "Trước khi đau có chấn thương, mang vác, tập luyện hoặc vận động tay lặp đi lặp lại nhiều hơn bình thường không?",
            "medium",
            ("mechanical_overuse_pathway",),
            "Chấn thương hoặc tải lặp lại có thể làm thay đổi cơ chế hợp lý nhất và cách tự chăm sóc ban đầu.",
        )

    if not any(marker in norm for marker in ("te tay", "te ngon", "yeu tay", "yeu ngon", "khong te", "khong yeu")):
        unknown(
            "hand_neurologic_features",
            "Bạn có tê, yếu bàn tay/ngón tay hoặc cầm nắm đồ vật khó hơn bình thường không?",
            "high",
            ("neurologic_evaluation",),
            "Tê hoặc yếu thật sự gợi ý cần xem thêm đường thần kinh, không nên quy toàn bộ triệu chứng cho riêng khớp.",
        )

    mechanisms: list[dict[str, Any]] = [
        {
            "hypothesis_id": "peripheral_joint_local_process",
            "label": "Đau có vẻ xuất phát từ khớp ngoại biên ở tay hơn là cột sống",
            "role": "leading",
            "support_level": "plausible",
            "mechanism": (
                "Đau khu trú ở các khớp bàn/ngón/cổ tay có thể liên quan tải cơ học của khớp và mô quanh khớp hoặc một quá trình viêm tại khớp; "
                "cần các dấu hiệu tại chỗ và diễn tiến để phân biệt tốt hơn."
            ),
            "evidence_for": [question],
            "evidence_against": [],
            "unresolved": [item["key"] for item in unknowns],
            "patient_safe_statement": (
                "Vị trí triệu chứng hiện phù hợp với một vấn đề ở khớp/mô quanh khớp của tay hơn là bệnh cảnh đau cột sống, nhưng hiện chưa đủ dữ kiện để xác định nguyên nhân."
            ),
        }
    ]

    next_unknown = next((item for item in unknowns if item["key"] == "fever_systemic_features"), None)
    local_unknown = next((item for item in unknowns if item["key"] == "joint_inflammation_pattern"), None)
    selected = local_unknown or next_unknown or (unknowns[0] if unknowns else None)

    episode = dict(episode_payload or {})
    episode["chief_domain"] = "peripheral_joint"
    episode["unknown_decision_relevant"] = unknowns
    episode["problem_representation"] = (
        "Bệnh cảnh khớp ngoại biên ở tay đang được làm rõ; chưa đủ dữ kiện để kết luận cơ chế viêm, cơ học, chấn thương hay thần kinh."
    )

    reasoning = {
        "version": "v27-peripheral-joint",
        "mechanisms": mechanisms,
        "leading_hypothesis_ids": ["peripheral_joint_local_process"],
        "must_not_miss_unknowns": [item["key"] for item in unknowns if item["impact"] == "critical"],
        "next_best_question": selected["question"] if selected else None,
        "next_question_key": selected["key"] if selected else None,
        "reasoning_limits": [
            "Cơ chế được mô tả là giả thuyết làm việc, không phải chẩn đoán xác định.",
            "Không được chuyển bệnh cảnh khớp tay sang reasoning cột sống chỉ vì cùng thuộc cơ-xương-khớp.",
            "Dữ kiện chưa được người dùng cung cấp phải giữ ở trạng thái unknown.",
        ],
    }
    return episode, reasoning


def _contextual_reasoning(question: str, urgency: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        episode = build_clinical_episode_model(
            episode_id="writer-active-episode",
            messages=_episode_messages(question),
        )
        episode = episode.model_copy(
            update={
                "latest_user_message": question,
                "active_episode_text": question,
            }
        )
        episode_payload = episode.to_agent_payload()
        if _peripheral_joint_signal(question):
            return _peripheral_joint_context(question, episode_payload)
        reasoning = build_contextual_reasoning_frame(episode, urgency=urgency)
        return episode_payload, reasoning.to_agent_payload()
    except Exception:
        return None, None


def _assessment_state(result: dict[str, Any], urgency: str) -> str:
    trace = result.get("trace") or {}
    details = trace.get("details") if isinstance(trace, dict) else {}
    details = details if isinstance(details, dict) else {}
    semantic_status = _text(details.get("semantic_status")).upper()
    source = _text(details.get("resolution_source")).lower()
    try:
        confidence = float(details.get("confidence", 1.0))
    except (TypeError, ValueError):
        confidence = 1.0

    if urgency == "EMERGENCY":
        return "SAFETY_ESCALATED"
    if semantic_status == "UNRESOLVED" or source in {"fail_safe", "epistemic_escalation", "needs_information_contract"}:
        return "INSUFFICIENT_CONTEXT"
    if semantic_status == "PARTIALLY_UNDERSTOOD" or confidence < 0.70:
        return "PARTIALLY_UNDERSTOOD"
    return "UNDERSTOOD"


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
        if assessment_state == "INSUFFICIENT_CONTEXT":
            add(
                "summary",
                "Hệ thống chưa có đủ dữ kiện để coi mức ROUTINE là một kết luận lâm sàng; cần làm rõ bệnh cảnh trước khi đưa ra nhận định chắc hơn.",
            )
        elif assessment_state == "PARTIALLY_UNDERSTOOD":
            add(
                "summary",
                "Bệnh cảnh mới được hiểu một phần; mức xử trí hiện tại phải được diễn đạt kèm giới hạn dữ kiện và câu hỏi làm rõ quan trọng nhất.",
            )
        else:
            add("summary", f"Mức xử trí tối thiểu đã được hệ thống an toàn xác định: {urgency}.")

        specialty = result.get("recommended_specialty")
        if isinstance(specialty, dict) and assessment_state not in {"INSUFFICIENT_CONTEXT"}:
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
            if assessment_state == "UNDERSTOOD":
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

    envelope = {
        "version": "v27-semantic-authority",
        "intent": intent,
        "user_question": question,
        "clinical_result": result,
        "assessment_state": assessment_state,
        "patient_context": _safe_patient_context(patient_context),
        "clinical_episode": episode_payload,
        "reasoning_frame": reasoning_payload,
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
            "question_budget": 0 if urgency == "EMERGENCY" else 1,
            "emergency_action_precedes_explanation": urgency == "EMERGENCY",
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
            "Treat unmentioned findings as unknown, never as negative findings.",
            "Do not convert an unresolved semantic match into a reassuring ROUTINE conclusion.",
            "Update the assessment from new facts instead of repeating the previous answer.",
            "If the patient proposes a dangerous action, interrupt and correct it before explaining why.",
            "Give a specific action plan and a clear threshold for seeking care.",
            "Ask only the single highest-information follow-up question when it can change management.",
            "Do not reuse fixed response templates or infer patient facts from rule antecedents.",
        ],
    }
    return ClinicalAgentContract(envelope=envelope, claims=claims)
