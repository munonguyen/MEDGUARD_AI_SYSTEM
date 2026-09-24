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


def _with_narrative(answer: GroundedAnswer, intent: ChatIntent) -> GroundedAnswer:
    """Turn bounded answer fields into prose without adding medical claims."""
    is_emergency = answer.title.startswith("Bạn cần được đánh giá cấp cứu")
    blocks = [
        _block(
            _as_sentences([answer.title, answer.summary]),
            kind="urgent" if is_emergency else "paragraph",
            emphasis=[answer.title],
        )
    ]

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

    visible_safety_notes = answer.safety_notes[:2]
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

    visible_next_steps = answer.next_steps
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

    visible_questions = answer.questions[:3]
    if visible_questions:
        prompt_label = "Thông tin cần báo nhân viên y tế nếu có thể" if is_emergency else "Bạn cho mình biết thêm"
        blocks.append(
            _block(
                f"{prompt_label}: {_as_sentences(visible_questions)}",
                emphasis=[prompt_label],
            )
        )

    res = answer.model_copy(update={"narrative": blocks})
    return _sanitize_clinical_response(res)


def _sanitize_clinical_response(answer: GroundedAnswer) -> GroundedAnswer:
    is_emergency = answer.title.startswith("Bạn cần được đánh giá cấp cứu")
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

    cleaned_blocks = []
    has_emergency_action = False
    for block in answer.narrative:
        text = block.text
        for phrase in forbidden_emergency_phrases:
            if phrase in text.lower():
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
                sentences = [s for s in sentences if phrase not in s.lower()]
                text = " ".join(sentences).strip()
        if text:
            if "115" in text or "cấp cứu" in text.lower():
                has_emergency_action = True
            cleaned_blocks.append(
                AnswerNarrativeBlock(
                    kind=block.kind,
                    text=text,
                    emphasis=block.emphasis,
                    source_ids=block.source_ids,
                )
            )

    # Invariant: An emergency response MUST explicitly instruct immediate emergency action
    if not has_emergency_action:
        cleaned_blocks.append(
            AnswerNarrativeBlock(
                kind="urgent",
                text="Hành động khẩn cấp: Hãy gọi ngay 115 hoặc nhờ người đưa đến khoa Cấp cứu bệnh viện gần nhất; tuyệt đối không tự lái xe hay trì hoãn tại nhà.",
                emphasis=["Gọi ngay 115", "khoa Cấp cứu"],
            )
        )

    return answer.model_copy(update={"narrative": cleaned_blocks})


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
        "EMERGENCY": "Bạn cần được đánh giá cấp cứu ngay",
        "URGENT": "Bạn nên được nhân viên y tế đánh giá sớm",
        "ROUTINE": "Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu",
    }
    urgency_labels = {"EMERGENCY": "cấp cứu", "URGENT": "khẩn", "ROUTINE": "thường quy"}
    key_points = [f"Mức phân luồng: {urgency_labels.get(urgency, urgency)}"]
    if esi:
        key_points.append(
            f"Mã ưu tiên nội bộ: ESI {esi} (đây là mức ưu tiên tiếp nhận, không phải xác suất chẩn đoán)"
        )
    if specialty_label:
        key_points.append(f"Hướng tiếp nhận do quy tắc lựa chọn: {specialty_label}")
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
                "Thông tin bạn mô tả khớp với dấu hiệu cảnh báo khẩn cấp trong quy tắc "
                "phân luồng. Bạn cần được nhân viên cấp cứu đánh giá ngay; hệ thống không "
                "xác định nguyên nhân hoặc chẩn đoán chỉ từ tin nhắn này."
            )
        # Emergency Override: strictly disable routine self-care and home monitoring advice
        next_steps = [
            "Dừng ngay mọi hoạt động đang làm hoặc gắng sức, ở nơi an toàn và nhờ người bên cạnh hỗ trợ trong khi liên hệ cấp cứu.",
            str(result.get("advice") or "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe."),
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
    elif urgency == "URGENT":
        summary = str(result.get("guidance_summary") or (
            "Các triệu chứng bạn mô tả cần được nhân viên y tế đánh giá trực tiếp sớm. "
            "Hệ thống không thể xác định nguyên nhân hoặc chẩn đoán chỉ từ tin nhắn; "
            "hãy ưu tiên hướng xử trí bên dưới."
        ))
        next_steps = [str(value) for value in result.get("self_care", [])]
        if result.get("advice"):
            next_steps.append(str(result["advice"]))
        questions = [str(value) for value in result.get("clarifying_questions", [])]
        safety_notes = [str(value) for value in result.get("safety_net", [])]
        clinical_hypotheses = [str(value) for value in result.get("clinical_hypotheses", [])]
    else:
        summary = str(result.get("guidance_summary") or (
            "Kết quả hiện tại chưa ghi nhận dấu hiệu nguy kịch ngay lúc này, tuy nhiên bạn cần "
            "theo dõi sát diễn biến và đi khám nếu triệu chứng kéo dài hoặc tăng nặng."
        ))
        next_steps = [str(value) for value in result.get("self_care", [])]
        if result.get("advice"):
            next_steps.append(str(result["advice"]))
        questions = [str(value) for value in result.get("clarifying_questions", [])]
        safety_notes = [str(value) for value in result.get("safety_net", [])]
        clinical_hypotheses = [str(value) for value in result.get("clinical_hypotheses", [])]

    return GroundedAnswer(
        title=titles.get(urgency, "Kết quả phân luồng"),
        summary=summary,
        clinical_hypotheses=clinical_hypotheses,
        key_points=key_points,
        next_steps=next_steps,
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
        ) + f"bộ quy tắc ghi nhận {len(hard_stops)} cảnh báo bắt buộc dừng và cần bác sĩ hoặc dược sĩ xác nhận."
    elif warnings:
        ingestion_warns = [w for w in warnings if w.get("type") == "REPORTED_ACUTE_INGESTION"]
        if ingestion_warns:
            summary = " ".join([str(w.get("detail", "")) + " " + str(w.get("recommendation", "")) for w in ingestion_warns]).strip()
        else:
            summary = f"Bộ quy tắc ghi nhận {len(warnings)} cảnh báo và xếp mức nguy cơ tổng thể là {risk}."
    else:
        summary = "Không tìm thấy cảnh báo trong dữ liệu đã nhập và bảng quy tắc hiện có. Kết quả này không chứng minh thuốc hoặc phối hợp thuốc là an toàn."
    key_points = []
    next_steps = []
    for warning in warnings:
        medication = f"{warning.get('medication')}: " if warning.get("medication") else ""
        point = f"{medication}{warning.get('detail') or warning.get('type', 'Cảnh báo thuốc')}"
        if warning.get("clinical_consequence"):
            point += f" Hệ quả được ghi nhận: {warning['clinical_consequence']}"
        key_points.append(point)
        # A HARD_STOP recommendation in the knowledge table may contain a
        # possible replacement drug. Do not surface it as personalized advice
        # from chat; the contraindication remains visible and a clinician or
        # pharmacist must select any alternative after reviewing the patient.
        if warning.get("recommendation") and warning.get("tier") != "HARD_STOP":
            next_steps.append(str(warning["recommendation"]))
    key_points.extend(f"Chưa xác định được hoạt chất: {value}" for value in unknown)
    requires_review = bool(result.get("requires_human_review"))
    if requires_review:
        next_steps.insert(0, "Không tự bắt đầu, ngừng hoặc phối hợp thuốc trước khi trao đổi với bác sĩ hoặc dược sĩ.")
    if hard_stops:
        next_steps.append("Hãy hỏi bác sĩ hoặc dược sĩ về lựa chọn thay thế phù hợp với bệnh nền và các thuốc bạn đang dùng.")
    questions = [str(value) for value in result.get("clarifying_questions", [])]
    return GroundedAnswer(
        title=titles.get(risk, "Kết quả kiểm tra thuốc"),
        summary=summary,
        key_points=key_points,
        next_steps=list(dict.fromkeys(next_steps)),
        questions=questions,
        decision_basis="versioned_rules",
        evidence_state="direct_rule_match" if warnings else "bounded_result",
        rule_version=_trace_rule_version(result),
        sources=relevant_sources,
        limitations=[
            "Kiểm tra chỉ bao phủ thuốc, hoạt chất, dị ứng và bệnh nền đã được cung cấp và có trong bảng tri thức hiện tại.",
            *_approval_limitations(relevant_sources),
        ],
        requires_human_review=requires_review,
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
        summary=f"Hệ thống đã đối chiếu chỉ số với ngưỡng cấu hình. Mức chuyển tuyến hiện tại: {escalation}; xu hướng: {result.get('trend', 'chưa xác định')}.",
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
    titles = {
        "registry_match": "Mã khớp với registry hiện tại",
        "suspected_counterfeit": "Mã có dấu hiệu không khớp",
        "recalled": "Sản phẩm nằm trong danh sách thu hồi",
        "expired": "Sản phẩm đã hết hạn theo registry",
        "unknown": "Chưa tìm thấy mã trong registry",
        "invalid": "Mã QR không hợp lệ",
    }
    points = [str(reason) for reason in result.get("reasons", [])]
    if product.get("name"):
        points.insert(0, f"Sản phẩm đối chiếu: {product['name']}")
    return GroundedAnswer(
        title=titles.get(status, "Kết quả đối chiếu mã"),
        summary="Kết quả phản ánh việc đối chiếu dữ liệu trong mã với registry đang kết nối, không phải kiểm định vật lý sản phẩm.",
        key_points=points,
        next_steps=["Không sử dụng sản phẩm và liên hệ nhà thuốc, nhà sản xuất hoặc cơ quan quản lý để xác minh."] if status != "registry_match" else [],
        decision_basis="registry_record",
        evidence_state="direct_rule_match" if status != "unknown" else "bounded_result",
        rule_version=_trace_rule_version(result),
        sources=sources,
        limitations=[
            "Mã khớp registry không tự chứng minh bao bì và thuốc bên trong là hàng thật.",
            *_approval_limitations(sources),
        ],
        requires_human_review=status != "registry_match",
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
    if not result:
        return _with_narrative(GroundedAnswer(
            title="Mình chưa thể xử lý yêu cầu này" if status == "unsupported" else "Kết quả xử lý",
            summary=reply,
            decision_basis="insufficient_information" if status == "unsupported" else "workflow_record",
            evidence_state="partial_input" if status == "unsupported" else "operation_confirmed",
            limitations=["Không có kết quả nghiệp vụ có cấu trúc để kiểm chứng thêm."],
        ), intent)

    sources = _sources(intent)
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
