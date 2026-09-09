"""Render user-facing answers strictly from bounded domain results."""

from __future__ import annotations

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

    if answer.safety_notes:
        safety_text = _as_sentences(answer.safety_notes)
        emergency_phrase = next(
            (value for value in answer.safety_notes if "cấp cứu ngay" in value.lower()),
            answer.safety_notes[0],
        )
        emergency_phrase = emergency_phrase.split(";")[0]
        blocks.append(
            _block(
                safety_text,
                kind="urgent" if is_emergency else "paragraph",
                emphasis=[emergency_phrase],
            )
        )

    if answer.next_steps:
        action_text = _as_sentences(answer.next_steps)
        blocks.append(
            _block(
                action_text,
                kind="urgent" if is_emergency else "paragraph",
                emphasis=[answer.next_steps[0] if is_emergency else ""],
            )
        )

    if answer.questions:
        blocks.append(
            _block(
                f"Bạn cho mình biết thêm: {_as_sentences(answer.questions)}",
                emphasis=["Bạn cho mình biết thêm"],
            )
        )

    return answer.model_copy(update={"narrative": blocks})


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


def _triage_answer(result: dict[str, Any], sources: list[ChatEvidenceSource]) -> GroundedAnswer:
    urgency = str(result.get("urgency", "ROUTINE"))
    esi = result.get("esi_level")
    specialty = result.get("recommended_specialty") or {}
    specialty_label = specialty.get("label")
    emergency = bool(result.get("emergency_flag"))
    titles = {
        "EMERGENCY": "Bạn cần được đánh giá cấp cứu ngay",
        "URGENT": "Bạn nên được nhân viên y tế đánh giá sớm",
        "ROUTINE": "Với thông tin hiện có, chưa thấy dấu hiệu cần cấp cứu ngay",
    }
    urgency_labels = {"EMERGENCY": "cấp cứu", "URGENT": "khẩn", "ROUTINE": "thường quy"}
    key_points = [f"Mức phân luồng: {urgency_labels.get(urgency, urgency)}" + (f", ESI {esi}" if esi else "")]
    if specialty_label:
        confidence = specialty.get("confidence")
        suffix = f" ({round(float(confidence) * 100)}% theo rule định tuyến)" if confidence is not None else ""
        key_points.append(f"Hướng tiếp nhận: {specialty_label}{suffix}")
    key_points.extend(f"Dấu hiệu được nhận diện: {flag}" for flag in result.get("red_flags", []))
    if emergency:
        summary = (
            "Thông tin bạn mô tả khớp với dấu hiệu cảnh báo khẩn cấp trong quy tắc "
            "phân luồng. Bạn cần được nhân viên cấp cứu đánh giá ngay; hệ thống không "
            "xác định nguyên nhân hoặc chẩn đoán chỉ từ tin nhắn này."
        )
    else:
        summary = str(result.get("guidance_summary") or (
            "Kết quả hiện tại chưa ghi nhận dấu hiệu nguy kịch ngay lúc này, tuy nhiên bạn cần "
            "theo dõi sát diễn biến và đi khám nếu triệu chứng kéo dài hoặc tăng nặng."
        ))
    next_steps = [str(value) for value in result.get("self_care", [])]
    if result.get("advice"):
        next_steps.append(str(result["advice"]))
    if emergency and not result.get("self_care"):
        next_steps.insert(
            0,
            "Dừng hoạt động đang làm, ở nơi an toàn và nhờ người bên cạnh hỗ trợ trong khi liên hệ cấp cứu.",
        )

    questions = [str(value) for value in result.get("clarifying_questions", [])]
    safety_notes = [str(value) for value in result.get("safety_net", [])]
    if not safety_notes and emergency:
        safety_notes = [
            "Không trì hoãn việc gọi 115 hoặc đến khoa Cấp cứu để chờ thêm triệu chứng hay tiếp tục trao đổi trực tuyến."
        ]

    return GroundedAnswer(
        title=titles.get(urgency, "Kết quả phân luồng"),
        summary=summary,
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
    warnings = result.get("warnings", [])
    unknown = result.get("unknown_ingredients", [])
    source_for_warning = {
        "DRUG_DRUG_INTERACTION": "drug_interactions.json",
        "ALLERGY_CROSS_REACTIVITY": "allergy_cross_matrix.json",
        "ALLERGY_PARTIAL_CROSS_REACTIVITY": "allergy_cross_matrix.json",
        "CONDITION_CONTRAINDICATION": "contraindications.json",
        "DUPLICATE_ACTIVE_INGREDIENT": "atc_codes.json",
    }
    relevant_source_names = {source_for_warning.get(str(warning.get("type"))) for warning in warnings}
    relevant_source_names.discard(None)
    relevant_sources = [source for source in sources if source.name in relevant_source_names] if relevant_source_names else sources
    titles = {
        "HIGH": "Có cảnh báo an toàn thuốc mức cao",
        "MODERATE": "Có cảnh báo cần kiểm tra trước khi dùng",
        "LOW": "Chưa tìm thấy cảnh báo trong phạm vi đã kiểm tra",
    }
    if warnings:
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
        if warning.get("recommendation"):
            next_steps.append(str(warning["recommendation"]))
    key_points.extend(f"Chưa xác định được hoạt chất: {value}" for value in unknown)
    requires_review = bool(result.get("requires_human_review"))
    if requires_review:
        next_steps.insert(0, "Không tự bắt đầu, ngừng hoặc phối hợp thuốc trước khi trao đổi với bác sĩ hoặc dược sĩ.")
    return GroundedAnswer(
        title=titles.get(risk, "Kết quả kiểm tra thuốc"),
        summary=summary,
        key_points=key_points,
        next_steps=list(dict.fromkeys(next_steps)),
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
        return _with_narrative(_triage_answer(result, sources), intent)
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
