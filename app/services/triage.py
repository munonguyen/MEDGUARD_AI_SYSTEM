from __future__ import annotations

from time import perf_counter

from app.core.context import RequestContext
from app.models.common import Status, Trace
from app.models.triage import RecommendedSpecialty, TriageRequest, TriageResponse
from app.knowledge.loader import knowledge
from app.services.audit import AuditEvent, audit_store
from app.services.clinical_text import contains_affirmed_phrase
from app.services.rules import triage_rules


def _tailor_guidance(
    guidance: dict,
    symptoms_text: str,
) -> tuple[str | None, list[str]]:
    summary = str(guidance.get("summary")) if guidance.get("summary") else None
    questions = [str(value) for value in guidance.get("clarifying_questions", [])]
    topic = guidance.get("topic")
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
    questions.insert(max(0, len(questions) - 1), follow_up)
    return summary, questions


def evaluate_triage(payload: TriageRequest, ctx: RequestContext) -> TriageResponse:
    start = perf_counter()
    rule = triage_rules(payload.symptoms_text, payload.vitals)
    guidance = knowledge.find_symptom_guidance(payload.symptoms_text)
    use_guidance = guidance is not None and not rule.emergency_flag
    guidance_summary, guidance_questions = (
        _tailor_guidance(guidance, payload.symptoms_text)
        if use_guidance and guidance is not None
        else (None, [])
    )
    clarifying_questions = guidance_questions if use_guidance else rule.clarifying_questions
    specialty = None
    if rule.recommended_specialty:
        specialty = RecommendedSpecialty(
            code=rule.recommended_specialty[0],
            label=rule.recommended_specialty[1],
            confidence=1.0 if rule.emergency_flag else 0.78,
        )
    response = TriageResponse(
        request_id=ctx.request_id,
        status=Status.ok,
        urgency=rule.urgency,  # type: ignore[arg-type]
        emergency_flag=rule.emergency_flag,
        esi_level=rule.esi_level,
        recommended_specialty=specialty,
        red_flags=rule.red_flags,
        clarifying_questions=clarifying_questions,
        self_care=[str(value) for value in guidance.get("self_care", [])] if use_guidance else [],
        safety_net=[str(value) for value in guidance.get("safety_net", [])] if use_guidance else [],
        guidance_summary=guidance_summary,
        advice=str(guidance.get("advice")) if use_guidance and guidance.get("advice") else rule.advice,
        trace=Trace(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            rule_version="triage-rules@pha0",
            knowledge_version=knowledge.version_string(),
            latency_ms=int((perf_counter() - start) * 1000),
            details={
                "severity_resolution": "rule-only",
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
