from __future__ import annotations

from time import perf_counter

from app.core.context import RequestContext
from app.models.common import Status, Trace
from app.models.triage import RecommendedSpecialty, TriageRequest, TriageResponse
from app.knowledge.loader import knowledge
from app.services.audit import AuditEvent, audit_store
from app.services.clinical_text import (
    contains_affirmed_phrase,
    extract_clinical_facts,
    filter_known_clarifying_questions,
)
from app.services.rules import triage_rules


def _tailor_guidance(
    guidance: dict,
    symptoms_text: str,
) -> tuple[str | None, list[str]]:
    summary = str(guidance.get("summary")) if guidance.get("summary") else None
    questions = [str(value) for value in guidance.get("clarifying_questions", [])]
    topic = str(guidance.get("topic", ""))
    if topic == "lower_limb_pain":
        norm = symptoms_text.lower()
        if summary and any(
            marker in norm
            for marker in ("worldcup", "world cup", "đi xem", "xem bóng đá", "xem bong da")
        ) and any(marker in norm for marker in ("khó đi", "kho di", "không đi được", "khong di duoc")):
            summary = (
                "Vì bạn đang đau chân đến mức khó đi, bạn không nên đi xem World Cup lúc này; "
                "việc đi bộ, đứng lâu hoặc chen trong đám đông có thể làm tình trạng nặng hơn. "
                "Cần làm rõ vị trí đau, nguyên nhân khởi phát và khả năng chịu lực để chọn mức chăm sóc phù hợp."
            )
        return summary, questions
    if topic == "muscle_strain_overexertion":
        norm = symptoms_text.lower()
        if any(w in norm for w in ("tay", "cánh tay", "bắp tay", "cổ tay")):
            summary = (
                "Tình trạng căng cơ tay sau khi vận sức hoặc mang vác quá mức thường xảy ra do các sợi cơ bị kéo giãn đột ngột vượt ngưỡng chịu tải. "
                "Hiện tại chưa thấy dấu hiệu nguy kịch, bạn nên tạm dừng gắng sức và áp dụng sơ cứu RICE (nghỉ ngơi, chườm lạnh, băng ép nhẹ) để cơ bắp sớm hồi phục."
            )
        elif any(w in norm for w in ("chân", "đùi", "bắp chân", "gối")):
            summary = (
                "Tình trạng căng cơ bắp chân sau vận động có thể phù hợp với quá tải hoặc kéo giãn cơ nhẹ, nhưng chưa thể xác định nguyên nhân chỉ từ tin nhắn. "
                "Hiện tại chưa thấy dấu hiệu nguy kịch, bạn nên dừng đi lại nhiều, thả lỏng chân và chườm mát để giảm căng tức."
            )
            questions = [
                "Đau nằm ở bắp chân, đùi, đầu gối hay cổ chân; bắt đầu ngay khi vận động hay sau đó?",
                "Bạn có đi và chịu lực bình thường không; vùng đau có sưng, bầm, đỏ nóng hoặc biến dạng không?",
                "Bạn có tê, yếu, chân lạnh hoặc đổi màu; hay đau và sưng một bên kèm đau ngực hoặc khó thở không?",
            ]
        return summary, questions
    if topic == "headache":
        norm = symptoms_text.lower()
        if any(w in norm for w in ("học", "hoc", "làm việc", "lam viec", "máy tính", "may tinh", "màn hình", "man hinh", "đọc sách", "doc sach", "thi cử", "thi cu", "căng thẳng", "cang thang", "áp lực", "ap luc", "deadline")):
            summary = (
                "Tình trạng nhức đầu xuất hiện khi học tập hoặc làm việc nhiều giờ thường do đau đầu dạng căng thẳng kết hợp mỏi điều tiết mắt (hội chứng thị giác màn hình) và co cứng cơ cổ gáy. "
                "Hiện tại chưa thấy dấu hiệu nguy kịch, bạn nên tạm dừng việc học ngay, rời khỏi màn hình/sách vở và cho mắt cùng não bộ nghỉ ngơi hoàn toàn 20-30 phút."
            )
        elif any(w in norm for w in ("ngủ dậy", "ngu day", "thức dậy", "thuc day", "buổi sáng", "buoi sang")):
            summary = (
                "Cơn đau đầu nhẹ hoặc ê ẩm khi mới ngủ dậy buổi sáng thường mang tính chất cấp tính nhẹ do căng cơ cổ khi ngủ sai tư thế, thiếu ngủ hoặc mất nước nhẹ qua đêm. "
                "Hiện chưa thấy dấu hiệu nguy kịch, bạn nên ưu tiên nghỉ ngơi, uống một cốc nước ấm và theo dõi thêm."
            )
        return summary, questions
    if topic == "neck_shoulder_pain":
        norm = symptoms_text.lower()
        if any(w in norm for w in ("ngủ dậy", "ngu day", "sáng", "sang", "âm ỉ", "am i", "cả ngày", "ca ngay")) and summary:
            summary += (
                " Triệu chứng mới xuất hiện khi ngủ dậy thường mang tính chất cấp tính nhẹ; bạn nên ưu tiên nghỉ ngơi, bù nước và theo dõi thêm trước khi lo lắng về các nguyên nhân phức tạp."
            )
        return summary, questions
    if topic == "back_pain":
        norm = symptoms_text.lower()
        if any(w in norm for w in ("học", "hoc", "ngồi", "ngoi", "làm việc", "lam viec", "khỏi luôn", "khoi luon", "ngay lập tức", "ngay lap tuc")):
            summary = (
                "Cơn đau mỏi thắt lưng xuất hiện trong lúc ngồi học hoặc làm việc lâu thường do quá tải cơ học và căng cơ dây chằng nâng đỡ cột sống. "
                "Tình trạng này không thể 'khỏi luôn ngay lập tức' bằng biện pháp cấp tốc, mà bạn cần lập tức đứng dậy rời bàn học, nằm nghỉ ngơi kê gối dưới khoeo chân để giải tỏa áp lực đĩa đệm. "
                "Hiện chưa ghi nhận dấu hiệu nguy kịch, bạn nên ưu tiên giảm tải tư thế và thư giãn cơ."
            )
        return summary, questions
    if topic == "open_wound_cut":
        norm = symptoms_text.lower()
        if any(w in norm for w in ("học", "hoc", "đau quá", "dau qua", "huhu", "hix", "lo quá", "lo qua", "sợ quá", "so qua")):
            summary = (
                "Đứt tay khi đang học hoặc sinh hoạt thường là vết cắt cấp tính do vật sắc nhọn (dao rọc giấy, mép giấy, kéo). "
                "Trước tiên bạn hãy bình tĩnh, không quá lo lắng; điều quan trọng nhất ngay bây giờ là bạn hãy dùng một miếng gạc hoặc khăn sạch ÉP CHẶT CẦM MÁU trực tiếp vào vết thương liên tục trong 5-10 phút (tránh mở ra xem giữa chừng). "
                "Hiện tại chưa thấy dấu hiệu nguy kịch, sau khi máu đã cầm bạn hãy thực hiện các bước sơ cứu và theo dõi các dấu hiệu cần đến cơ sở y tế bên dưới."
            )
        return summary, questions
    if topic == "acute_burn":
        norm = symptoms_text.lower()
        if any(w in norm for w in ("rát quá", "rat qua", "đau quá", "dau qua", "nước sôi", "nuoc soi", "dầu", "dau", "bô xe", "bo xe")):
            summary = (
                "Tình trạng bỏng nhiệt thường gây cảm giác đau rát buốt dữ dội. "
                "Hành động cấp thiết nhất bạn cần làm NGAY BÂY GIỜ là đưa ngay vùng da bị bỏng vào xả nhẹ nhàng dưới vòi nước sạch mát liên tục trong 15-20 phút để chặn đứng sự tổn thương mô lan sâu. "
                "Tuyệt đối không chườm đá lạnh buốt hay bôi kem đánh răng, mỡ trăn hay nước mắm lên vết bỏng."
            )
        return summary, questions
    if topic == "nosebleed_epistaxis":
        summary = (
            "Chảy máu cam thường xuất phát từ các mao mạch nông ở vách ngăn mũi. "
            "Bạn hãy bình tĩnh ngồi thẳng người, hơi cúi đầu nhẹ về phía trước và dùng hai ngón tay bóp chặt hai cánh mũi liên tục 10-15 phút để cầm máu; "
            "tuyệt đối không ngửa cổ ra sau để tránh máu chảy ngược xuống họng gây sặc."
        )
        return summary, questions
    if topic == "ankle_sprain":
        summary = (
            "Tình trạng lật sơ mi hoặc trẹo cổ chân sau vận động hay bước hụt thường do căng giãn hoặc rách dây chằng quanh khớp. "
            "Hiện tại chưa thấy dấu hiệu nguy kịch, bạn hãy dừng ngay việc đi lại, không dồn lực lên chân và áp dụng biện pháp chườm lạnh kết hợp kê cao chân; tuyệt đối không xoa dầu nóng."
        )
        return summary, questions
    if topic == "dizziness_presyncope":
        summary = (
            "Cơn chóng mặt, hoa mắt hoặc xây xẩm thường do căng thẳng, hạ huyết áp tư thế hoặc hạ đường huyết nhẹ. "
            "Bạn cần lập tức ngồi bệt xuống hoặc nằm nghỉ ngơi nơi thoáng mát, hạ thấp đầu để tránh té ngã chấn thương; uống một cốc nước ấm có chút đường và theo dõi thêm."
        )
        return summary, questions
    if topic == "insect_bite_sting":
        summary = (
            "Vết đốt của ong hoặc côn trùng thường gây phản ứng sưng đỏ đau buốt cấp tính tại chỗ. "
            "Bạn hãy rửa sạch ngay dưới vòi nước xà phòng, chườm lạnh để giảm đau sưng và theo dõi sát các phản ứng toàn thân."
        )
        return summary, questions
    if topic == "scabies_dermatology":
        summary = (
            "Bệnh ghẻ là bệnh nhiễm ký sinh trùng cái ghẻ đào hang dưới da gây ngứa dữ dội (đặc biệt về đêm) và lây lan rất nhanh. "
            "Hiện tại chưa thấy dấu hiệu nguy kịch, bệnh này hoàn toàn có thể chữa khỏi dứt điểm nhưng bắt buộc phải dùng đúng thuốc bôi diệt ghẻ đặc hiệu, "
            "đồng thời giặt luộc khử trùng toàn bộ chăn màn quần áo và điều trị cùng lúc cho tất cả người sống chung."
        )
        return summary, questions

    if topic not in {"abdominal_pain", "upper_abdominal_discomfort"}:
        return summary, questions
    if not contains_affirmed_phrase(symptoms_text, "buồn nôn"):
        return summary, questions

    if summary:
        summary += (
            " Bạn cũng đã mô tả cảm giác buồn nôn; cần làm rõ liệu đã nôn, "
            "có uống được nước hay không và có dấu hiệu cảnh báo đi kèm không."
        )
    follow_up = (
        "Bạn đã mô tả buồn nôn; bạn đã nôn chưa, có uống được nước không, "
        "và có sốt, đầy hơi, ợ chua, tiêu chảy, táo bón, chướng hoặc cứng bụng không?"
    )
    questions = [question for question in questions if "buồn nôn" not in question]
    # Narrative rendering intentionally limits follow-up prompts to three.
    # Put the user's newly reported symptom inside that visible priority set.
    questions.insert(min(2, len(questions)), follow_up)
    return summary, questions


from app.services.semantic_risk import safe_semantic_evaluate, semantic_risk_evaluator
from app.services.triage_resolver import resolve_triage


def evaluate_triage(
    payload: TriageRequest,
    ctx: RequestContext,
    *,
    conversation_risk: str | None = None,
) -> TriageResponse:
    start = perf_counter()
    rule = triage_rules(payload.symptoms_text, payload.vitals)
    facts = extract_clinical_facts(payload.symptoms_text)

    from app.services.dose_reasoning import evaluate_dose_reasoning
    from app.services.toxicology_reasoner import evaluate_toxicology, ToxicologyUrgency
    from app.services.compositional_reasoner import evaluate_compositional_risk
    from app.services.clinical_fact_parser import parse_semantic_clinical_facts
    from app.services.partial_evidence_safety import evaluate_partial_evidence_safety

    dose_assessment = evaluate_dose_reasoning(payload.symptoms_text)
    tox_assessment = evaluate_toxicology(payload.symptoms_text)
    is_emergency_tox = (tox_assessment.urgency == ToxicologyUrgency.EMERGENCY)
    fact_set = getattr(facts, "fact_set", None) or parse_semantic_clinical_facts(payload.symptoms_text)
    vitals_dict = payload.vitals.model_dump(exclude_none=True) if payload.vitals else None
    comp_hypothesis = evaluate_compositional_risk(fact_set, vitals_dict)
    partial_safety = evaluate_partial_evidence_safety(payload.symptoms_text, vitals_dict, fact_set=fact_set)

    # Hybrid Conservative Resolution across Rule, Compositional Threat Reasoner, Semantic Evaluator, Partial Safety, Dose, and Multi-turn
    # 1. Fast-path: Explicit Emergency from deterministic rule, dose toxicity, toxicology reasoner, threat graph, or partial safety
    if (
        rule.urgency == "EMERGENCY"
        or (dose_assessment and dose_assessment.urgency == "EMERGENCY")
        or is_emergency_tox
        or comp_hypothesis.disposition == "EMERGENCY"
        or partial_safety.has_partial_emergency_threat
    ):
        semantic_result = None
        source_label = "dose" if (dose_assessment and dose_assessment.urgency == "EMERGENCY") else ("toxicology" if is_emergency_tox else ("rule" if rule.urgency == "EMERGENCY" else ("compositional" if comp_hypothesis.disposition == "EMERGENCY" else "partial_safety")))
        resolved = resolve_triage(
            rule_urgency="EMERGENCY" if rule.urgency == "EMERGENCY" else None,
            compositional_urgency="EMERGENCY" if comp_hypothesis.disposition == "EMERGENCY" else None,
            partial_safety_urgency="EMERGENCY" if partial_safety.has_partial_emergency_threat else None,
            semantic_urgency="EMERGENCY" if ((dose_assessment and dose_assessment.urgency == "EMERGENCY") or is_emergency_tox) else None,
            historical_urgency=conversation_risk,
            rule_confidence=rule.confidence,
            compositional_confidence=comp_hypothesis.risk_confidence,
            partial_safety_confidence=partial_safety.confidence,
            fact_coverage=fact_set.semantic_coverage,
        )
    # 2. Fast-path: High-Confidence Explicit Benign Pattern from deterministic rule or benign gate
    elif (rule.urgency == "ROUTINE" and rule.matched and rule.confidence >= 0.95 and not partial_safety.safety_floor) or (comp_hypothesis.disposition == "ROUTINE" and comp_hypothesis.risk_confidence >= 0.98 and not conversation_risk and not partial_safety.safety_floor):
        semantic_result = None
        resolved = resolve_triage(
            rule_urgency="ROUTINE" if rule.matched else None,
            compositional_urgency="ROUTINE" if comp_hypothesis.disposition == "ROUTINE" else None,
            semantic_urgency=None,
            historical_urgency=conversation_risk,
            rule_confidence=rule.confidence,
            compositional_confidence=comp_hypothesis.risk_confidence,
            fact_coverage=fact_set.semantic_coverage,
        )
    # 3. Otherwise: Invoke Semantic Clinical Risk Evaluator
    else:
        semantic_result = safe_semantic_evaluate(
            semantic_risk_evaluator,
            payload.symptoms_text,
            clinical_facts=facts,
        )
        if semantic_result and not semantic_result.uncertain:
            sem_status = "UNDERSTOOD"
        elif fact_set.semantic_coverage >= 0.70:
            sem_status = "UNDERSTOOD"
        elif fact_set.semantic_coverage >= 0.30 or (semantic_result and semantic_result.confidence >= 0.70):
            sem_status = "PARTIALLY_UNDERSTOOD"
        else:
            sem_status = "UNRESOLVED"
        has_functional_loss = fact_set.has_functional_loss(["loss_of_sight", "loss_of_motor_power", "inability_to_speak_full_sentences", "inability_to_tolerate_palpation_movement", "loss_of_limb_perfusion"])

        resolved = resolve_triage(
            rule_urgency=rule.urgency if rule.urgency != "UNRESOLVED" else None,
            compositional_urgency=comp_hypothesis.disposition if comp_hypothesis.disposition != "ROUTINE" else None,
            partial_safety_urgency=partial_safety.safety_floor,
            partial_safety_confidence=partial_safety.confidence,
            semantic_urgency=semantic_result.urgency if semantic_result else None,
            historical_urgency=conversation_risk,
            rule_confidence=rule.confidence if rule.matched else 0.50,
            semantic_confidence=semantic_result.confidence if semantic_result else 0.50,
            compositional_confidence=comp_hypothesis.risk_confidence,
            semantic_status=sem_status,
            fact_coverage=fact_set.semantic_coverage,
            has_acute_functional_loss=has_functional_loss,
        )

    final_urgency = resolved.urgency
    emergency_flag = (final_urgency == "EMERGENCY")

    # Merge red flags from rule and semantic evaluation
    merged_red_flags = list(rule.red_flags)
    if semantic_result:
        for rf in semantic_result.red_flags:
            if rf not in merged_red_flags:
                merged_red_flags.append(rf)

    # Determine aligned ESI level
    esi_level = rule.esi_level
    if final_urgency == "EMERGENCY" and (esi_level is None or esi_level > 2):
        esi_level = 2
    elif final_urgency == "URGENT" and (esi_level is None or esi_level > 3):
        esi_level = 3
    elif final_urgency == "ROUTINE" and esi_level is None:
        esi_level = 4

    guidance = knowledge.find_symptom_guidance(payload.symptoms_text)
    use_guidance = guidance is not None and (
        final_urgency == "ROUTINE" or guidance.get("topic") == "lower_limb_pain"
    )
    guidance_summary, guidance_questions = (
        _tailor_guidance(guidance, payload.symptoms_text)
        if use_guidance and guidance is not None
        else (None, [])
    )
    clarifying_questions = guidance_questions if use_guidance else rule.clarifying_questions
    if emergency_flag:
        clarifying_questions = []
    else:
        clarifying_questions = filter_known_clarifying_questions(clarifying_questions, facts)

    clinical_hypotheses = (
        [str(item) for item in guidance.get("clinical_hypotheses", [])]
        if use_guidance and guidance
        else []
    )
    specialty = None
    if rule.recommended_specialty:
        specialty = RecommendedSpecialty(
            code=rule.recommended_specialty[0],
            label=rule.recommended_specialty[1],
            confidence=1.0 if emergency_flag else 0.78,
        )

    advice = rule.advice
    if final_urgency == "EMERGENCY" and rule.urgency != "EMERGENCY":
        advice = "Tình trạng có dấu hiệu nguy kịch cần liên hệ cấp cứu 115 hoặc đến cơ sở y tế gần nhất ngay lập tức."
    elif final_urgency == "URGENT" and rule.urgency in ("ROUTINE", "UNRESOLVED"):
        advice = "Nên được nhân viên y tế đánh giá sớm trong ngày; nếu triệu chứng nặng lên, hãy đến cơ sở cấp cứu."
    elif use_guidance and guidance and guidance.get("advice"):
        advice = str(guidance.get("advice"))

    response = TriageResponse(
        request_id=ctx.request_id,
        status=Status.ok,
        urgency=final_urgency,  # type: ignore[arg-type]
        emergency_flag=emergency_flag,
        esi_level=esi_level,
        recommended_specialty=specialty,
        red_flags=merged_red_flags,
        clarifying_questions=clarifying_questions,
        self_care=[str(value) for value in guidance.get("self_care", [])] if use_guidance else [],
        safety_net=[str(value) for value in guidance.get("safety_net", [])] if use_guidance else [],
        guidance_summary=guidance_summary,
        clinical_hypotheses=clinical_hypotheses,
        advice=advice,
        trace=Trace(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            rule_version="triage-rules@pha0",
            knowledge_version=knowledge.version_string(),
            latency_ms=int((perf_counter() - start) * 1000),
            details={
                "severity_resolution": "hybrid-conservative-max",
                "rule_urgency": rule.urgency,
                "rule_matched": rule.matched,
                "semantic_urgency": semantic_result.urgency if semantic_result else None,
                "conversation_risk": conversation_risk,
                "resolution_source": resolved.source,
                "confidence": resolved.confidence,
                "semantic_status": resolved.semantic_status.value if hasattr(resolved.semantic_status, "value") else str(resolved.semantic_status),
                "symptom_guidance": guidance.get("topic") if use_guidance else None,
                "knowledge_integrity": knowledge.integrity_report(),
            },
        ),
    )
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="triage.evaluate",
            payload_type=payload.__class__.__name__,
            metadata={"urgency": response.urgency, "emergency_flag": response.emergency_flag},
        )
    )
    return response
