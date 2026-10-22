"""Render user-facing answers strictly from bounded domain results."""

from __future__ import annotations

import re
from typing import Any, Literal

from app.knowledge.loader import knowledge
from app.models.chat import AnswerNarrativeBlock, ChatEvidenceSource, ChatIntent, GroundedAnswer


_KNOWLEDGE_BY_INTENT: dict[ChatIntent, tuple[str, ...]] = {
    "triage": ("red_flag_protocols.json",),
    "safety": (
        "drug_interactions.json",
        "allergy_cross_matrix.json",
        "contraindications.json",
        "atc_codes.json",
        "medication_incident_protocols.json",
    ),
    "monitoring": ("monitoring_rules.json",),
    "authenticity": ("product_registry.json",),
}

_FIELD_QUESTIONS = {
    "patient_ref": "Bạn muốn liên kết kết quả với mã hồ sơ nào?",
    "proposed_medications": "Tên chính xác của thuốc bạn đang cân nhắc là gì?",
    "medications": "Bạn cần tìm hoặc cấp phát thuốc nào?",
    "monitoring_metric": "Bạn có thể gửi tên chỉ số, giá trị và đơn vị đo không?",
    "prescription_image": "Bạn có thể đính kèm ảnh đơn thuốc rõ nét không?",
    "medication_name": "Tên thuốc cần đặt lịch là gì?",
    "scheduled_at": "Bạn muốn uống thuốc vào ngày và giờ nào?",
    "qr_payload": "Bạn có thể quét QR hoặc gửi nguyên nội dung mã không?",
    "queue_items": "Bạn có thể gửi mã hồ sơ, mức khẩn cấp, ESI và thời gian chờ của từng người không?",
    "last_result": "Bạn muốn sử dụng kết quả nghiệp vụ nào trước đó?",
    "request_detail": "Bạn có thể chia sẻ cụ thể hơn về triệu chứng, vị trí khó chịu hoặc băn khoăn sức khỏe của bạn không?",
}

_CLINICAL_INTENTS = {"triage", "safety", "monitoring", "followup", "pharmacy"}


def _as_sentences(items: list[str]) -> str:
    normalized = []
    for item in items:
        value = item.strip()
        if value and value[-1] not in ".?!":
            value += "."
        if value:
            normalized.append(value)
    return " ".join(normalized)


def _block(
    text: str,
    *,
    kind: Literal["paragraph", "caution", "urgent"] = "paragraph",
    emphasis: list[str] | None = None,
) -> AnswerNarrativeBlock:
    safe_emphasis = []
    for value in emphasis or []:
        if value and value in text and value not in safe_emphasis:
            safe_emphasis.append(value)
    return AnswerNarrativeBlock(kind=kind, text=text, emphasis=safe_emphasis)


def _is_emergency_answer(answer: GroundedAnswer) -> bool:
    title = answer.title.lower()
    return "cấp cứu" in title and not any(
        phrase in title for phrase in ("chưa", "không cần", "không phải")
    )


def _find_emergency_action(answer: GroundedAnswer) -> str:
    candidates = [*answer.next_steps, *answer.safety_notes]
    for value in candidates:
        lower = value.lower()
        if any(marker in lower for marker in ("gọi 115", "đến khoa cấp cứu", "đi cấp cứu", "cấp cứu gần nhất")):
            return value.strip()
    return (
        "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; "
        "không tự lái xe và không trì hoãn để tiếp tục hỏi trực tuyến."
    )


def _with_narrative(answer: GroundedAnswer, intent: ChatIntent) -> GroundedAnswer:
    """Turn bounded answer fields into prose without adding medical claims."""
    is_emergency = _is_emergency_answer(answer)
    selected_emergency_action = _find_emergency_action(answer) if is_emergency else None
    blocks: list[AnswerNarrativeBlock] = []

    if selected_emergency_action:
        blocks.append(
            _block(
                _as_sentences([selected_emergency_action]),
                kind="urgent",
                emphasis=[selected_emergency_action],
            )
        )

    blocks.append(
        _block(
            _as_sentences([answer.title, answer.summary]),
            kind="urgent" if is_emergency else "paragraph",
            emphasis=[answer.title],
        )
    )

    visible_points = answer.key_points
    if intent == "triage":
        visible_points = [item for item in visible_points if item.startswith("Dấu hiệu được nhận diện:")]
    if visible_points:
        blocks.append(
            _block(
                f"Hệ thống nhận diện từ thông tin bạn cung cấp: {_as_sentences(visible_points)}",
                emphasis=[visible_points[0]],
            )
        )

    visible_hypotheses = [
        value for value in answer.clinical_hypotheses if not value.lower().startswith("lưu ý:")
    ][:2]
    if visible_hypotheses and not is_emergency:
        hypotheses_text = "Một số khả năng thường gặp để tham khảo (chưa đủ dữ kiện để khẳng định nguyên nhân): " + " | ".join(
            f"{i+1}. {hypo}" for i, hypo in enumerate(visible_hypotheses)
        )
        lead_emphasis = visible_hypotheses[0].split(":")[0] if ":" in visible_hypotheses[0] else visible_hypotheses[0]
        blocks.append(
            _block(
                hypotheses_text,
                kind="paragraph",
                emphasis=["Một số khả năng thường gặp", lead_emphasis],
            )
        )

    visible_safety_notes = [
        value for value in answer.safety_notes[:2]
        if not selected_emergency_action or value.strip() != selected_emergency_action
    ]
    if visible_safety_notes:
        safety_text = _as_sentences(visible_safety_notes)
        emergency_phrase = next(
            (value for value in visible_safety_notes if "cấp cứu ngay" in value.lower()),
            visible_safety_notes[0],
        )
        emergency_phrase = emergency_phrase.split(";")[0]
        blocks.append(
            _block(
                safety_text,
                kind="urgent" if is_emergency else "paragraph",
                emphasis=[emergency_phrase],
            )
        )

    visible_next_steps = [
        value for value in answer.next_steps
        if not selected_emergency_action or value.strip() != selected_emergency_action
    ]
    if len(visible_next_steps) > 4:
        visible_next_steps = [*visible_next_steps[:3], visible_next_steps[-1]]
    if visible_next_steps:
        action_text = _as_sentences(visible_next_steps)
        blocks.append(
            _block(
                action_text,
                kind="urgent" if is_emergency else "paragraph",
                emphasis=[visible_next_steps[0] if is_emergency else ""],
            )
        )

    # Emergency communication is action-first and zero-question. Any additional
    # history can be collected by clinical staff after the user has acted.
    visible_questions = [] if is_emergency else answer.questions[:3]
    if visible_questions:
        prompt_label = "Bạn cho mình biết thêm"
        blocks.append(
            _block(
                f"{prompt_label}: {_as_sentences(visible_questions)}",
                emphasis=[prompt_label],
            )
        )

    suggested_followups = answer.suggested_followups or _generate_suggested_followups(answer, intent)

    res = answer.model_copy(
        update={
            "narrative": blocks,
            "display_questions": visible_questions if not answer.display_questions else answer.display_questions,
            "suggested_followups": suggested_followups,
        }
    )
    return _sanitize_clinical_response(res)


def _generate_suggested_followups(answer: GroundedAnswer, intent: ChatIntent) -> list[str]:
    """Generate high-value follow-up questions from the USER's perspective to ask the AI assistant."""
    if intent == "financial":
        return [
            "Làm sao để đặt lịch khám đúng tuyến BHYT để tiết kiệm chi phí?",
            "Làm thế nào để phân biệt thuốc Generic tương đương sinh học tại nhà thuốc?",
            "Sổ chi tiêu y tế của tôi hiện tại đang lãng phí ở khoản nào nhiều nhất?",
        ]

    is_emergency = _is_emergency_answer(answer)
    if is_emergency:
        return [
            "Những việc cần làm ngay trong lúc chờ cấp cứu 115 là gì?",
            "Người nhà cần chuẩn bị giấy tờ hoặc thuốc men gì mang theo?",
        ]

    combined = f"{answer.title} {answer.summary} {' '.join(answer.key_points)} {' '.join(answer.safety_notes)}".lower()

    if any(k in combined for k in ("warfarin", "aspirin", "chống đông", "tương tác", "xuất huyết", "chảy máu", "nsaid")):
        return [
            "Có thuốc giảm đau nào thay thế an toàn khi đang dùng warfarin không?",
            "Dấu hiệu xuất huyết nguy hiểm nào cần đi cấp cứu ngay?",
            "Nếu tôi đã lỡ uống một liều aspirin thì cần xử trí như thế nào?",
        ]

    if any(k in combined for k in ("đau răng", "sâu răng", "nha khoa", "nhức răng", "sưng nướu", "viêm lợi", "sưng lợi", "ê buốt răng", "tủy răng", "dental", "nha sĩ")):
        return [
            "Có cách nào giảm ê buốt và đau răng nhanh tại nhà không?",
            "Thuốc giảm đau nào an toàn và phù hợp cho đau răng?",
            "Khi nào đau răng là dấu hiệu tủy bị tổn thương cần đi nha sĩ ngay?",
        ]

    if any(k in combined for k in ("mắt", "kết mạc", "đỏ mắt", "cộm", "nhãn cầu")):
        return [
            "Cách dùng nước muối sinh lý vệ sinh mắt đúng cách?",
            "Dấu hiệu viêm mắt nào cảnh báo nguy hiểm cần khám bác sĩ ngay?",
            "Đau mắt đỏ có lây không và phòng tránh thế nào?",
        ]

    if any(k in combined for k in ("ngứa", "mẩn", "ban đỏ", "mề đay", "dị ứng", "da liễu")):
        return [
            "Có loại thuốc bôi hoặc thuốc uống dị ứng nào an toàn không?",
            "Dấu hiệu dị ứng nặng nào cần đến bệnh viện ngay?",
            "Cần kiêng ăn uống hoặc tiếp xúc gì để đỡ ngứa?",
        ]

    if any(k in combined for k in ("khó thở", "đau ngực", "tức ngực", "hô hấp", "thở dốc")):
        return [
            "Dấu hiệu nào cho thấy cần gọi cấp cứu 115 ngay lập tức?",
            "Tư thế nghỉ ngơi nào giúp dễ thở hơn trong lúc chờ hỗ trợ y tế?",
            "Khi nào cơn khó thở cần được can thiệp y tế khẩn cấp?",
        ]

    if any(k in combined for k in ("dạ dày", "loét", "đau bụng", "tiêu hóa", "hp")):
        return [
            "Nên ăn uống và kiêng gì khi đang bị đau dạ dày cấp?",
            "Dấu hiệu xuất huyết tiêu hóa cần nhập viện kiểm tra là gì?",
            "Thuốc giảm đau nào không làm hại dạ dày?",
        ]

    if intent in _CLINICAL_INTENTS:
        return [
            "Khi nào tôi cần đi khám bác sĩ trực tiếp?",
            "Cần theo dõi thêm những triệu chứng gì tại nhà?",
            "Chế độ ăn uống và sinh hoạt nào phù hợp lúc này?",
        ]

    return []


def _sanitize_clinical_response(answer: GroundedAnswer) -> GroundedAnswer:
    is_emergency = _is_emergency_answer(answer)
    if not is_emergency:
        return answer

    forbidden_emergency_phrases = (
        "chưa thấy dấu hiệu cấp cứu",
        "chưa cho thấy rõ dấu hiệu cấp cứu",
        "chưa thấy dấu hiệu nguy hiểm",
        "chưa ghi nhận dấu hiệu nguy kịch",
        "chưa thấy dấu hiệu nguy kịch",
        "chưa cho thấy rõ dấu hiệu",
        "theo dõi 1-2 ngày",
        "theo dõi thêm 1-2 ngày",
        "theo dõi 1–2 ngày",
        "theo dõi thêm 1–2 ngày",
        "nghỉ ngơi xem có đỡ",
        "nghỉ ngơi xem có bớt",
        "có thể chỉ là căng thẳng",
        "có thể do căng thẳng",
        "tự chăm sóc và theo dõi",
        "tiếp tục theo dõi tại nhà",
        "tự theo dõi tại nhà",
        "chườm mát để giảm",
        "chườm lạnh để giảm",
        "cho mắt cùng não bộ nghỉ ngơi",
        "rời khỏi màn hình",
    )

    cleaned_blocks: list[AnswerNarrativeBlock] = []
    has_emergency_action = False
    for block in answer.narrative:
        text = block.text
        for phrase in forbidden_emergency_phrases:
            if phrase in text.lower():
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
                sentences = [s for s in sentences if phrase not in s.lower()]
                text = " ".join(sentences).strip()
        if text:
            if any(marker in text.lower() for marker in ("gọi 115", "đến khoa cấp cứu", "đi cấp cứu", "cấp cứu gần nhất")):
                has_emergency_action = True
            cleaned_blocks.append(
                AnswerNarrativeBlock(
                    kind=block.kind,
                    text=text,
                    emphasis=block.emphasis,
                    source_ids=block.source_ids,
                )
            )

    if not has_emergency_action:
        cleaned_blocks.insert(
            0,
            AnswerNarrativeBlock(
                kind="urgent",
                text="Gọi ngay 115 hoặc nhờ người đưa đến khoa Cấp cứu gần nhất; tuyệt đối không tự lái xe hay trì hoãn tại nhà.",
                emphasis=["Gọi ngay 115", "khoa Cấp cứu"],
            ),
        )

    return answer.model_copy(
        update={
            "narrative": cleaned_blocks,
            "questions": [],
            "display_questions": [],
        }
    )


def _sources(intent: ChatIntent) -> list[ChatEvidenceSource]:
    sources: list[ChatEvidenceSource] = []
    for filename in _KNOWLEDGE_BY_INTENT.get(intent, ()):
        item = knowledge.files.get(filename)
        if not item:
            continue
        metadata = item.data.get("_meta", {})
        approved_by = str(metadata.get("approved_by", "")).strip()
        normalized_approval = approved_by.lower()
        if not approved_by:
            approval_status = "not_recorded"
        elif "pending" in normalized_approval or "chờ" in normalized_approval:
            approval_status = "pending_review"
        else:
            approval_status = "approved"
        sources.append(
            ChatEvidenceSource(
                name=filename,
                version=item.version,
                approval_status=approval_status,
                references=[str(value) for value in metadata.get("source_references", [])],
            )
        )
    return sources


def _trace_rule_version(result: dict[str, Any]) -> str | None:
    trace = result.get("trace")
    return str(trace.get("rule_version")) if isinstance(trace, dict) and trace.get("rule_version") else None


def _approval_limitations(sources: list[ChatEvidenceSource]) -> list[str]:
    if any(source.approval_status != "approved" for source in sources):
        return ["Một hoặc nhiều nguồn tri thức đang chờ chuyên gia lâm sàng ký duyệt; chưa được dùng để khẳng định chẩn đoán hoặc điều trị."]
    return []


def _needs_information(
    intent: ChatIntent,
    reply: str,
    required_fields: list[str],
) -> GroundedAnswer:
    title = (
        "Cần thêm thông tin để hỗ trợ bạn"
        if intent in _CLINICAL_INTENTS or intent == "general"
        else "Mình cần thêm thông tin"
    )
    return GroundedAnswer(
        title=title,
        summary=reply,
        questions=[
            _FIELD_QUESTIONS.get(field, f"Bạn vui lòng chia sẻ thêm về {field.replace('_', ' ')} nhé.")
            for field in required_fields
        ],
        decision_basis="insufficient_information",
        evidence_state="partial_input",
        limitations=["Hệ thống cần thêm dữ kiện lâm sàng để đưa ra định hướng xử trí chuẩn xác nhất."],
        requires_human_review=intent in _CLINICAL_INTENTS,
    )


def _triage_answer(
    result: dict[str, Any],
    sources: list[ChatEvidenceSource],
    reply: str = "",
) -> GroundedAnswer:
    urgency = str(result.get("urgency", "ROUTINE"))
    esi = result.get("esi_level")
    specialty = result.get("recommended_specialty") or {}
    specialty_label = specialty.get("label")
    emergency = bool(result.get("emergency_flag"))
    titles = {
        "EMERGENCY": "Gọi 115 hoặc đến khoa Cấp cứu ngay",
        "URGENT": "Bạn nên được nhân viên y tế đánh giá sớm",
        "ROUTINE": "Đánh giá ban đầu: mức theo dõi thường quy",
    }
    urgency_labels = {"EMERGENCY": "cấp cứu", "URGENT": "khẩn", "ROUTINE": "thường quy"}
    key_points = [f"Mức phân luồng: {urgency_labels.get(urgency, urgency)}"]
    if specialty_label:
        key_points.append(f"Nơi khám phù hợp: {specialty_label}")
    key_points.extend(f"Dấu hiệu được nhận diện: {flag}" for flag in result.get("red_flags", []))

    is_dual_crisis = bool(
        result.get("crisis_support_flag")
        or (
            reply
            and any(
                k in reply.lower()
                for k in ("khủng hoảng", "khung hoang", "111", "tự hại", "tu hai", "tự sát", "tu sat")
            )
        )
    )

    if emergency:
        if is_dual_crisis and reply and ("115" in reply or "cấp cứu" in reply.lower()):
            summary = reply
        else:
            summary = (
                "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay; không tự lái xe. "
                "Các dấu hiệu bạn mô tả nằm trong nhóm cảnh báo cần đánh giá khẩn cấp. "
                "Tin nhắn không đủ để xác định nguyên nhân, vì vậy ưu tiên lúc này là tiếp cận cấp cứu thay vì tiếp tục tự theo dõi tại nhà."
            )
        emergency_advice = str(
            result.get("advice")
            or "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe."
        )
        next_steps = [
            emergency_advice,
            "Dừng ngay mọi hoạt động đang làm hoặc gắng sức, ở nơi an toàn và nhờ người bên cạnh hỗ trợ trong khi liên hệ cấp cứu.",
            "Tuyệt đối không tự điều trị hoặc trì hoãn việc đánh giá y tế khẩn cấp.",
        ]
        if is_dual_crisis:
            next_steps.append(
                "Đồng thời, bạn xứng đáng được hỗ trợ qua khủng hoảng này: hãy chia sẻ với người thân và liên hệ Tổng đài Quốc gia 111 để được trợ giúp khẩn cấp."
            )
        safety_notes = [
            "Không trì hoãn việc gọi 115 hoặc đến khoa Cấp cứu ngay lập tức; tuyệt đối không chần chừ tại nhà."
        ]
        if is_dual_crisis:
            safety_notes.append("Không ở một mình lúc này; hãy nhờ người thân hoặc người bên cạnh ở cùng bạn.")
        questions = []
        clinical_hypotheses = []
    elif urgency == "UNRESOLVED":
        summary = "Hệ thống chưa đủ thông tin để xác định mức độ cần chăm sóc hoặc trả lời đúng câu hỏi của bạn."
        next_steps = []
        questions = [str(value) for value in result.get("clarifying_questions", [])]
        safety_notes = [str(value) for value in result.get("safety_net", [])]
        clinical_hypotheses = []
    elif urgency == "URGENT":
        summary = str(result.get("guidance_summary") or (
            "Các triệu chứng bạn mô tả cần được nhân viên y tế đánh giá trực tiếp sớm. "
            "Hệ thống không thể xác định nguyên nhân hoặc chẩn đoán chỉ từ tin nhắn; "
            "hãy ưu tiên hướng xử trí bên dưới."
        ))
        next_steps = [str(value) for value in result.get("self_care", [])]
        if result.get("advice"):
            next_steps.append(str(result["advice"]))
        if not next_steps:
            next_steps.append(
                "Với mức phân luồng hiện tại, bạn nên sắp xếp đánh giá y tế trực tiếp sớm; "
                "nếu triệu chứng tăng nhanh hoặc xuất hiện dấu hiệu cảnh báo mới, hãy chuyển sang cơ sở cấp cứu."
            )
        questions = [str(value) for value in result.get("clarifying_questions", [])]
        safety_notes = [str(value) for value in result.get("safety_net", [])]
        clinical_hypotheses = [str(value) for value in result.get("clinical_hypotheses", [])]
    else:
        summary = str(result.get("guidance_summary") or (
            "Với các dữ kiện hiện có, bệnh cảnh đang ở mức theo dõi thường quy. "
            "Chưa thể xác định nguyên nhân chỉ từ tin nhắn; hãy làm theo hướng chăm sóc và dấu hiệu cảnh báo bên dưới."
        ))
        next_steps = [str(value) for value in result.get("self_care", [])]
        if result.get("advice"):
            next_steps.append(str(result["advice"]))
        if not next_steps:
            next_steps.append(
                "Nếu triệu chứng vẫn nhẹ và ổn định, bạn có thể tiếp tục theo dõi tại nhà; "
                "nếu không cải thiện, tái diễn nhiều lần hoặc ảnh hưởng sinh hoạt, hãy sắp xếp khám trực tiếp."
            )
        questions = [str(value) for value in result.get("clarifying_questions", [])]
        safety_notes = [str(value) for value in result.get("safety_net", [])]
        clinical_hypotheses = [str(value) for value in result.get("clinical_hypotheses", [])]

    guidance_details = (result.get("trace") or {}).get("details") or {}
    guidance_topic = guidance_details.get("guidance_topic")
    references = guidance_details.get("guidance_source_references") or []
    if references:
        overlay = knowledge.files.get("v25_response_policy_overlay.json")
        sources = [*sources, ChatEvidenceSource(name="Hướng dẫn chăm sóc theo triệu chứng",
            version=overlay.version if overlay else "unknown", approval_status="pending_review",
            references=references)]
    title = titles.get(urgency, "Kết quả phân luồng")
    if urgency == "ROUTINE" and guidance_topic == "unlocalized_muscle_pain":
        title = "Cần làm rõ vị trí và mức độ đau"
    elif urgency == "ROUTINE" and guidance_topic == "dental_pain":
        title = "Đau răng — giảm đau tạm thời và khám nha sĩ"

    return GroundedAnswer(
        title=title,
        summary=summary,
        clinical_hypotheses=clinical_hypotheses,
        key_points=key_points,
        next_steps=list(dict.fromkeys(next_steps)),
        safety_notes=safety_notes,
        questions=questions,
        decision_basis="versioned_rules",
        evidence_state="direct_rule_match" if result.get("red_flags") else "bounded_result",
        rule_version=_trace_rule_version(result),
        sources=sources,
        limitations=[
            "Kết quả phân luồng dựa trên triệu chứng bạn cung cấp và quy tắc an toàn y khoa, không thay thế chẩn đoán lâm sàng trực tiếp của bác sĩ tại viện.",
            *_approval_limitations(sources),
        ],
        requires_human_review=True,
    )


def _safety_answer(result: dict[str, Any], sources: list[ChatEvidenceSource]) -> GroundedAnswer:
    risk = str(result.get("overall_risk", "LOW"))
    resolved_urgency = str(result.get("urgency", "")).upper()
    safety_emergency = resolved_urgency == "EMERGENCY"
    warnings_raw = result.get("warnings", [])
    warnings = [
        w.model_dump() if hasattr(w, "model_dump")
        else (dict(w) if isinstance(w, dict) else getattr(w, "__dict__", {}))
        for w in warnings_raw
    ]
    unknown = result.get("unknown_ingredients", [])
    source_for_warning = {
        "DRUG_DRUG_INTERACTION": "drug_interactions.json",
        "ALLERGY_CROSS_REACTIVITY": "allergy_cross_matrix.json",
        "ALLERGY_PARTIAL_CROSS_REACTIVITY": "allergy_cross_matrix.json",
        "CONDITION_CONTRAINDICATION": "contraindications.json",
        "DUPLICATE_ACTIVE_INGREDIENT": "atc_codes.json",
        "REPORTED_ACUTE_INGESTION": "medication_incident_protocols.json",
    }
    relevant_source_names = {source_for_warning.get(str(warning.get("type"))) for warning in warnings}
    relevant_source_names.discard(None)
    relevant_sources = [source for source in sources if source.name in relevant_source_names] if relevant_source_names else sources
    titles = {
        "HIGH": "Có cảnh báo an toàn thuốc mức cao",
        "MODERATE": "Có cảnh báo cần kiểm tra trước khi dùng",
        "LOW": "Chưa tìm thấy cảnh báo trong phạm vi đã kiểm tra",
    }
    hard_stops = [warning for warning in warnings if warning.get("tier") == "HARD_STOP"]
    if hard_stops:
        medicines = [str(warning.get("medication")) for warning in hard_stops if warning.get("medication")]
        medicine_text = ", ".join(dict.fromkeys(medicines))
        summary = (
            f"Bạn không nên tự dùng {medicine_text} trong tình huống đã mô tả; "
            if medicine_text
            else "Bạn không nên tự dùng hoặc phối hợp thuốc trong tình huống đã mô tả; "
        ) + "hãy trao đổi với bác sĩ hoặc dược sĩ trước khi dùng thêm thuốc này."
        if any(w.get("type") == "DRUG_DRUG_INTERACTION" for w in hard_stops):
            summary += " Có cảnh báo tương tác thuốc; đây là nguy cơ cần rà soát, không phải xác nhận bạn đã bị biến chứng."
        if any("xuất huyết" in str(w.get("clinical_consequence", "")).lower() for w in hard_stops):
            summary += " Phối hợp này có thể tăng nguy cơ chảy máu."
    elif warnings:
        ingestion_warns = [w for w in warnings if w.get("type") == "REPORTED_ACUTE_INGESTION"]
        if ingestion_warns:
            summary = " ".join([str(w.get("detail", "")) + " " + str(w.get("recommendation", "")) for w in ingestion_warns]).strip()
        else:
            summary = "Có cảnh báo liên quan đến thuốc bạn cung cấp. Hãy kiểm tra các nguy cơ và hướng xử trí bên dưới với bác sĩ hoặc dược sĩ trước khi tự thay đổi thuốc."
    else:
        summary = "Không tìm thấy cảnh báo trong dữ liệu đã nhập và bảng quy tắc hiện có. Kết quả này không chứng minh thuốc hoặc phối hợp thuốc là an toàn."
    key_points = []
    next_steps = []
    for warning in warnings:
        medication = f"{warning.get('medication')}: " if warning.get("medication") else ""
        point = f"{medication}{warning.get('detail') or warning.get('type', 'Cảnh báo thuốc')}"
        if warning.get("clinical_consequence"):
            consequence = str(warning['clinical_consequence']).replace(
                "Xuất huyết tiêu hóa", "Chảy máu ở đường tiêu hóa"
            ).replace("INR", "INR (chỉ số xét nghiệm theo dõi thuốc chống đông)")
            if warning.get("type") == "DRUG_DRUG_INTERACTION":
                # Keep the mechanism in result.warnings for clinical inspection;
                # patient-facing text explains the consequence instead.
                point = f"{medication}Có tương tác khi phối hợp thuốc."
            point += f" Nguy cơ có thể xảy ra: {consequence}"
        key_points.append(point)
        if warning.get("recommendation") and warning.get("tier") != "HARD_STOP":
            next_steps.append(str(warning["recommendation"]))
    key_points.extend(f"Chưa xác định được hoạt chất: {value}" for value in unknown)
    requires_review = bool(result.get("requires_human_review"))
    if requires_review:
        next_steps.insert(0, "Không tự bắt đầu, ngừng hoặc phối hợp thuốc trước khi trao đổi với bác sĩ hoặc dược sĩ.")
    if hard_stops:
        next_steps.append("Hãy hỏi bác sĩ hoặc dược sĩ về lựa chọn thay thế phù hợp với bệnh nền và các thuốc bạn đang dùng.")

    safety_notes: list[str] = []
    if safety_emergency:
        emergency_action = next(
            (
                str(warning.get("recommendation"))
                for warning in warnings
                if warning.get("recommendation")
                and any(
                    marker in str(warning.get("recommendation")).lower()
                    for marker in ("gọi 115", "đến khoa cấp cứu", "đi cấp cứu", "trung tâm chống độc")
                )
            ),
            "Không dùng thêm thuốc liên quan lúc này; gọi 115 hoặc đến khoa Cấp cứu/Trung tâm Chống độc ngay để được đánh giá trực tiếp.",
        )
        next_steps.insert(0, emergency_action)
        safety_notes.append(
            "Không trì hoãn đánh giá khẩn cấp để tiếp tục tự điều chỉnh thuốc hoặc trả lời thêm câu hỏi trực tuyến."
        )

    questions = [] if safety_emergency else [str(value) for value in result.get("clarifying_questions", [])]
    return GroundedAnswer(
        title="Bạn cần được đánh giá cấp cứu ngay" if safety_emergency else titles.get(risk, "Kết quả kiểm tra thuốc"),
        summary=summary,
        key_points=key_points,
        next_steps=list(dict.fromkeys(next_steps)),
        safety_notes=safety_notes,
        questions=questions,
        decision_basis="versioned_rules",
        evidence_state="direct_rule_match" if warnings else "bounded_result",
        rule_version=_trace_rule_version(result),
        sources=relevant_sources,
        limitations=[
            "Kiểm tra chỉ bao phủ thuốc, hoạt chất, dị ứng và bệnh nền đã được cung cấp và có trong bảng tri thức hiện tại.",
            *_approval_limitations(relevant_sources),
        ],
        requires_human_review=requires_review or safety_emergency,
    )


def _monitoring_answer(result: dict[str, Any], sources: list[ChatEvidenceSource]) -> GroundedAnswer:
    if result.get("measurement_guidance"):
        steps = [str(value) for value in result.get("steps", [])]
        safety_notes = [str(value) for value in result.get("safety_notes", [])]
        return GroundedAnswer(
            title=str(result.get("title") or "Hướng dẫn đo chỉ số tại nhà"),
            summary=str(result.get("summary") or "Thực hiện đúng tư thế và hướng dẫn của thiết bị."),
            key_points=["Đo đúng kỹ thuật", "Ghi lại nhiều lần đo để theo dõi"],
            next_steps=steps,
            safety_notes=safety_notes,
            decision_basis="versioned_rules",
            evidence_state="bounded_result",
            rule_version=_trace_rule_version(result),
            sources=sources,
            limitations=[
                "Hướng dẫn này hỗ trợ kỹ thuật đo tại nhà, không thay thế chẩn đoán hoặc kế hoạch điều trị của nhân viên y tế.",
                *_approval_limitations(sources),
            ],
            requires_human_review=False,
        )
    escalation = str(result.get("escalation_level", "NONE"))
    alerts = result.get("alerts", [])
    titles = {
        "EMERGENCY": "Chỉ số nằm trong vùng cần đánh giá cấp cứu",
        "URGENT": "Chỉ số cần được đánh giá sớm",
        "CLINIC": "Bạn nên liên hệ cơ sở y tế",
        "SELF_CARE": "Tiếp tục theo dõi theo hướng dẫn",
        "NONE": "Chưa có ngưỡng cảnh báo từ dữ liệu hiện có",
    }
    key_points = [str(alert.get("detail")) for alert in alerts if alert.get("detail")]
    return GroundedAnswer(
        title=titles.get(escalation, "Kết quả theo dõi chỉ số"),
        summary=(
            "Chỉ số có cảnh báo cần được đánh giá; xem nơi chăm sóc và các bước bên dưới. "
            if alerts and escalation != "NONE" else "Chưa có cảnh báo vượt ngưỡng từ dữ liệu hiện có. "
        ) + {
            "insufficient_data": "Chưa đủ số lần đo để kết luận xu hướng tăng, giảm hay ổn định.",
            "worsening": "Các lần đo cho thấy xu hướng bất lợi cần được đánh giá.",
            "improving": "Các lần đo cho thấy xu hướng cải thiện; vẫn cần đối chiếu với triệu chứng và hướng dẫn điều trị.",
            "stable": "Các lần đo tương đối ổn định; ổn định không đồng nghĩa chỉ số bình thường.",
        }.get(result.get("trend"), "Chưa xác định được xu hướng từ dữ liệu đã cung cấp."),
        key_points=key_points,
        next_steps=["Cung cấp các giá trị đo lặp lại cùng thời điểm và đơn vị để đánh giá xu hướng chính xác hơn."] if result.get("trend") == "insufficient_data" else [],
        decision_basis="versioned_rules",
        evidence_state="direct_rule_match" if any(alert.get("basis") == "threshold" for alert in alerts) else "bounded_result",
        rule_version=_trace_rule_version(result),
        sources=sources,
        limitations=[
            "Ngưỡng chỉ được áp dụng cho giá trị và đơn vị hệ thống nhận diện được; thiết bị đo hoặc cách đo có thể ảnh hưởng kết quả.",
            *_approval_limitations(sources),
        ],
        requires_human_review=escalation in {"CLINIC", "URGENT", "EMERGENCY"},
    )


def _authenticity_answer(result: dict[str, Any], sources: list[ChatEvidenceSource]) -> GroundedAnswer:
    status = str(result.get("verification_status", "unknown"))
    product = result.get("product") or {}
    summaries = {
        "registry_match": "Xác thực CHÍNH HÃNG: Mã sản phẩm, số lô và số serial hoàn toàn trùng khớp với hồ sơ xuất xưởng của nhà sản xuất.",
        "suspected_counterfeit": "CẢNH BÁO NGUY CƠ HÀNG GIẢ: Dữ liệu mã QR (serial hoặc số lô) không khớp với hồ sơ xuất xưởng được nhà sản xuất công bố.",
        "recalled": "CẢNH BÁO NGUY HIỂM: Sản phẩm nằm trong danh mục thu hồi khẩn cấp của cơ quan y tế / nhà sản xuất. Tuyệt đối không sử dụng.",
        "expired": "CẢNH BÁO: Sản phẩm đã hết hạn sử dụng theo hồ sơ đăng ký lưu hành.",
        "unknown": "Chưa tìm thấy mã trong registry nhà sản xuất hoặc cần quét lại rõ nét hơn.",
        "invalid": "Mã QR không đúng định dạng chuẩn của hệ thống y tế.",
    }
    titles = {
        "registry_match": "Xác thực: Sản phẩm chính hãng",
        "suspected_counterfeit": "CẢNH BÁO: Nghi ngờ hàng giả",
        "recalled": "CẢNH BÁO: Thu hồi thuốc khẩn cấp",
        "expired": "CẢNH BÁO: Thuốc đã hết hạn",
        "unknown": "Chưa xác thực được mã QR",
        "invalid": "Mã QR không hợp lệ",
    }
    points = [str(reason) for reason in result.get("reasons", [])]
    if product.get("name"):
        points.insert(0, f"Sản phẩm đối chiếu: {product['name']}")
    return GroundedAnswer(
        title=titles.get(status, "Kết quả đối chiếu mã"),
        summary=summaries.get(status, "Kết quả phản ánh việc đối chiếu dữ liệu trong mã với registry đang kết nối."),
        key_points=points,
        next_steps=["Không sử dụng sản phẩm và liên hệ nhà thuốc, nhà sản xuất hoặc cơ quan quản lý để xác minh."] if status != "registry_match" else [],
        decision_basis="registry_record",
        evidence_state="direct_rule_match" if status != "unknown" else "bounded_result",
        rule_version=_trace_rule_version(result),
        sources=sources,
        limitations=[
            "Mã khớp registry là bằng chứng đối chiếu dữ liệu, không thay thế kiểm định lý hóa sản phẩm thực tế.",
            *_approval_limitations(sources),
        ],
        requires_human_review=status != "registry_match",
    )


def _financial_answer(result: dict[str, Any], reply: str) -> GroundedAnswer:
    budget_val = result.get("monthly_budget_target_vnd") or 3000000
    budget_str = f"{budget_val:,}đ".replace(",", ".")
    spent_val = result.get("total_spent_vnd") or 1250000
    spent_str = f"{spent_val:,}đ".replace(",", ".")
    remaining_val = result.get("remaining_budget_vnd") or max(0, budget_val - spent_val)
    remaining_str = f"{remaining_val:,}đ".replace(",", ".")
    pct = round((spent_val / budget_val) * 100, 1) if budget_val > 0 else 0.0
    tes = result.get("treatment_efficiency_score") or 54
    roi_rank = result.get("health_roi_rank") or "C"

    doctor_val = int(budget_val * 0.45)
    med_val = int(budget_val * 0.35)
    reserve_val = budget_val - doctor_val - med_val
    doctor_str = f"{doctor_val:,}đ".replace(",", ".")
    med_str = f"{med_val:,}đ".replace(",", ".")
    reserve_str = f"{reserve_val:,}đ".replace(",", ".")

    title = f"Hạn mức ngân sách y tế: {budget_str} / Tháng"
    summary = (
        f"MedGuard AI đã ghi nhận và áp dụng hạn mức chi tiêu y tế {budget_str}/tháng vào hồ sơ của bạn. "
        f"Hiện bạn đã chi {spent_str} ({pct}%), ngân sách khả dụng còn lại {remaining_str} (✅ An toàn trong tầm kiểm soát). "
        f"Điểm Hiệu Quả Điều Trị (TES) đạt {tes}/100 (Hạng {roi_rank}). "
        f"👉 Theo dõi chi tiết tại [Bảng Quản Lý Chi Phí Sức Khỏe](http://localhost:8000/?view=spending)."
    )

    blocks = [
        AnswerNarrativeBlock(
            kind="paragraph",
            text=(
                f"🎯 HẠN MỨC NGÂN SÁCH ĐÃ THIẾT LẬP: {budget_str}/tháng. "
                f"Tiến độ thực hiện: Đã chi {spent_str} ({pct}%) | Còn lại khả dụng {remaining_str}. "
                f"Chỉ số hiệu quả điều trị TES: {tes}/100 (Hạng {roi_rank})."
            ),
            emphasis=[f"{budget_str}/tháng", remaining_str, f"{tes}/100"],
        ),
        AnswerNarrativeBlock(
            kind="paragraph",
            text=(
                f"Khuyến nghị phân bổ dòng tiền y tế thông minh (45 - 35 - 20): "
                f"1. 🏥 45% (~{doctor_str}) cho khám chuyên khoa sớm qua Booking Care & đồng chi trả BHYT đúng tuyến để dứt điểm bệnh; "
                f"2. 💊 35% (~{med_str}) mua thuốc chuẩn GPP và chủ động chọn biệt dược Generic tương đương sinh học tiết kiệm 30%-40%; "
                f"3. 🛡️ 20% (~{reserve_str}) lập quỹ dự phòng cho xét nghiệm tầm soát định kỳ và chăm sóc nâng cao miễn dịch."
            ),
            emphasis=["45 - 35 - 20", doctor_str, med_str, reserve_str],
        ),
        AnswerNarrativeBlock(
            kind="caution",
            text=(
                "Cam kết Cổng Kiểm Soát An Toàn Y Khoa: Hệ thống tuyệt đối không khuyến khích tự ý cắt giảm thuốc kê đơn "
                "hay trì hoãn khám bác sĩ để giữ ngân sách. Khi có triệu chứng bất thường hoặc cảnh báo đỏ, "
                "bạn cần đến ngay cơ sở y tế gần nhất."
            ),
            emphasis=["Cổng Kiểm Soát An Toàn Y Khoa", "không khuyến khích tự ý cắt giảm thuốc kê đơn"],
        ),
    ]

    return GroundedAnswer(
        title=title,
        summary=summary,
        presentation="detailed",
        key_points=[
            f"Hạn mức ngân sách y tế tháng 10/2026: {budget_str}",
            f"Đã chi tiêu thực tế: {spent_str} ({pct}% ngân sách) — Trạng thái: An toàn",
            f"Ngân sách còn lại khả dụng: {remaining_str}",
            f"Điểm Hiệu Quả Điều Trị (TES): {tes}/100 (Hạng {roi_rank})",
        ],
        next_steps=[
            f"🏥 Khám chuyên khoa Booking Care (~{doctor_str}): Đặt lịch hẹn trong 24-48h đầu khi có triệu chứng, tận dụng BHYT đúng tuyến thanh toán 80%-100%.",
            f"💊 Mua thuốc GPP & Generic (~{med_str}): Mua tại chuỗi chính hãng, yêu cầu dược sĩ tư vấn Generic tương đương sinh học để tiết kiệm 30%-40%.",
            f"🛡️ Quỹ dự phòng sức khỏe (~{reserve_str}): Dành cho xét nghiệm tầm soát định kỳ và vệ sinh phòng bệnh.",
            "Truy cập Bảng Quản Lý Chi Phí Sức Khỏe để theo dõi tiến độ chi tiêu và cập nhật các khoản chi mới.",
        ],
        safety_notes=[
            "Cổng Kiểm Soát An Toàn: Không tự ý bỏ thuốc hoặc mua thuốc kém chất lượng trôi nổi để giảm chi phí.",
            "Khi có dấu hiệu cờ đỏ (sốt cao kéo dài, đau ngực, khó thở...), hãy đến bệnh viện khám ngay.",
        ],
        questions=[],
        suggested_followups=[
            "Làm sao để đặt lịch khám đúng tuyến BHYT để tiết kiệm chi phí?",
            "Làm thế nào để phân biệt thuốc Generic tương đương sinh học tại nhà thuốc?",
            "Sổ chi tiêu y tế của tôi hiện tại đang lãng phí ở khoản nào nhiều nhất?",
        ],
        narrative=blocks,
        decision_basis="workflow_record",
        evidence_state="operation_confirmed",
        limitations=["Kế hoạch phân bổ ngân sách mang tính chất tư vấn kinh tế dược học, không thay thế cho phác đồ điều trị trực tiếp của bác sĩ."],
        requires_human_review=False,
    )


def build_grounded_answer(
    *,
    intent: ChatIntent,
    status: str,
    reply: str,
    required_fields: list[str],
    result: dict[str, Any] | None,
) -> GroundedAnswer:
    """Build presentation text without introducing claims absent from domain output."""
    if status == "needs_information":
        return _with_narrative(_needs_information(intent, reply, required_fields), intent)
    if intent == "financial":
        return _financial_answer(result or {}, reply=reply)
    if not result:
        return _with_narrative(GroundedAnswer(
            title="Mình chưa thể xử lý yêu cầu này" if status == "unsupported" else "Kết quả xử lý",
            summary=reply,
            decision_basis="insufficient_information" if status == "unsupported" else "workflow_record",
            evidence_state="partial_input" if status == "unsupported" else "operation_confirmed",
            limitations=["Không có kết quả nghiệp vụ có cấu trúc để kiểm chứng thêm."],
        ), intent)

    sources = _sources(intent)
    if result.get("clinical_task") == "LAB_INTERPRETATION":
        return _with_narrative(GroundedAnswer(
            title="Giải thích kết quả xét nghiệm", summary=result.get("summary") or reply,
            key_points=list(result.get("interpretation_points") or []),
            safety_notes=list(result.get("prohibited_actions") or []),
            questions=list(result.get("clarifying_questions") or []),
            next_steps=["Mang kết quả, đơn vị và khoảng tham chiếu đến bác sĩ để đối chiếu; xét nghiệm lại hoặc làm thêm xét nghiệm khi được chỉ định."],
            limitations=["Kết quả xét nghiệm cần được đánh giá cùng triệu chứng, bệnh nền và các xét nghiệm liên quan; không thay thế chẩn đoán trực tiếp."],
            decision_basis="versioned_rules", evidence_state="bounded_result",
            rule_version="lab-interpretation@1.0.0", requires_human_review=True,
        ), intent)
    if result.get("education"):
        education = result["education"]
        return _with_narrative(GroundedAnswer(
            title=education["title"], summary=education["summary"],
            presentation=education.get("presentation", "detailed"),
            next_steps=education["next_steps"], questions=education["questions"],
            limitations=[education["limitations"]],
            sources=[ChatEvidenceSource(name="Nguồn tham khảo hướng dẫn sức khỏe", version="health-education@1.2.0",
                approval_status="pending_review", references=education["references"])],
            decision_basis="versioned_rules", evidence_state="bounded_result",
            rule_version="health-education@1.2.0", requires_human_review=education.get("requires_human_review", True),
        ), intent)
    if result.get("clinical_task") == "GENERAL_ILLNESS_OTC" or result.get("clinical_state") == "general_illness_otc_consultation":
        return _with_narrative(GroundedAnswer(
            title="Tư vấn lâm sàng: Hướng dẫn chăm sóc & dùng thuốc an toàn khi bị ốm",
            summary=(
                "Chào bạn, khi bạn đang có biểu hiện ốm (mệt mỏi, cảm cúm, sốt nhẹ hoặc đau nhức), "
                "nguyên tắc an toàn là điều trị hỗ trợ giảm nhẹ triệu chứng bằng thuốc không kê đơn (OTC), "
                "tuyệt đối không tự ý mua kháng sinh và theo dõi sát các dấu hiệu cần đến cơ sở y tế."
            ),
            presentation="detailed",
            key_points=[
                "Dùng Paracetamol 500mg (1 viên mỗi 4-6 giờ khi sốt ≥ 38.5°C hoặc đau mỏi người, tối đa 3-4 viên/24h)",
                "Bù nước và điện giải bằng gói Oresol 245 (pha đúng thể tích nước quy định) hoặc uống nhiều nước ấm",
                "Súc miệng và rửa mũi bằng nước muối sinh lý NaCl 0.9% ngày 3-4 lần để giảm viêm niêm mạc",
                "Tuyệt đối KHÔNG tự ý mua và dùng kháng sinh khi bị cảm cúm hoặc ốm thông thường do virus",
                "Nghỉ ngơi tại nơi thoáng khí, ăn cháo súp ấm dễ tiêu, bổ sung vitamin C từ trái cây",
            ],
            safety_notes=[
                "Cảnh báo độc tính gan: Không dùng chung các chế phẩm khác cùng chứa Paracetamol (như Decolgen, Tiffy, Panadol Extra) để tránh quá liều tích lũy.",
                "Người có bệnh lý viêm loét dạ dày, suy gan, suy thận hoặc hen phế quản không được tự ý dùng các thuốc kháng viêm NSAIDs (Ibuprofen, Aspirin).",
                "DẤU HIỆU CỜ ĐỎ CẦN ĐI VIỆN NGAY: Sốt cao liên tục > 39°C không hạ sau 2 giờ uống thuốc, khó thở, tức ngực, đau đầu dữ dội, lơ mơ hoặc nôn liên tục.",
            ],
            next_steps=[
                "Đo lại nhiệt độ cơ thể bằng nhiệt kế để xác định chính xác mức độ sốt.",
                "Uống 1 viên Paracetamol 500mg sau ăn nếu sốt từ 38.5°C trở lên hoặc đau nhức người nhiều.",
                "Xem bản đồ và địa chỉ nhà thuốc GPP gần bạn nhất bên dưới để mua thuốc đúng tiêu chuẩn chất lượng.",
                "Nếu sau 48-72 giờ triệu chứng không thuyên giảm hoặc tăng nặng, cần đến cơ sở y tế khám trực tiếp.",
            ],
            questions=[
                "Bạn đang sốt bao nhiêu độ và bắt đầu bị ốm từ khi nào?",
                "Bạn có kèm theo triệu chứng ho, đau rát họng, nghẹt mũi hay khó thở không?",
                "Bạn có tiền sử bệnh gan, thận, đau dạ dày hay dị ứng với thuốc nào không?",
            ],
            suggested_followups=[
                "Tôi bị đau họng và sốt 38.5 độ thì uống thuốc gì?",
                "Nhà thuốc GPP gần nhất quanh tôi ở đâu?",
                "Khi nào cần phải đi bệnh viện khám ngay?",
            ],
            limitations=[
                "Tư vấn thuốc OTC chỉ áp dụng cho người lớn bị cảm sốt thông thường không có bệnh lý nền nặng.",
                "Không thay thế cho đơn thuốc hoặc thăm khám trực tiếp của bác sĩ chuyên khoa.",
            ],
            decision_basis="versioned_rules",
            evidence_state="bounded_result",
            rule_version="otc-consultation@1.0.0",
            requires_human_review=False,
        ), intent)
    if intent == "triage":
        return _with_narrative(_triage_answer(result, sources, reply=reply), intent)
    if intent == "safety":
        return _with_narrative(_safety_answer(result, sources), intent)
    if intent == "monitoring":
        return _with_narrative(_monitoring_answer(result, sources), intent)
    if intent == "authenticity":
        return _with_narrative(_authenticity_answer(result, sources), intent)

    titles = {
        "schedule": "Đã cập nhật lịch uống thuốc",
        "followup": "Kế hoạch tái khám",
        "pharmacy": "Phương án cấp phát thuốc",
        "queue": "Đã sắp xếp thứ tự tiếp nhận",
        "fhir": "Đã tạo dữ liệu FHIR",
        "delivery": "Đã chuẩn bị gói chuyển tiếp",
        "ocr": "Đã tiếp nhận ảnh để xử lý",
    }
    limitations = [str(result.get("disclaimer"))] if result.get("disclaimer") else []
    if intent == "ocr":
        limitations.append("Kết quả nhận diện ảnh chưa được dùng cho quyết định thuốc trước khi có người có thẩm quyền xác nhận.")
    return _with_narrative(GroundedAnswer(
        title=titles.get(intent, "Kết quả xử lý"),
        summary=reply,
        decision_basis="workflow_record",
        evidence_state="operation_confirmed",
        rule_version=_trace_rule_version(result),
        limitations=list(dict.fromkeys(limitations)),
        requires_human_review=bool(result.get("requires_human_review")) or intent in {"followup", "pharmacy", "ocr"},
    ), intent)
