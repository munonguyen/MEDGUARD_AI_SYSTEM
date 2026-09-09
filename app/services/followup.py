from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from time import perf_counter

from app.core.context import RequestContext
from app.models.common import Status, Trace
from app.models.followup import FollowUpPlanResponse, FollowUpRequest, FollowUpSuggestion
from app.services.audit import AuditEvent, audit_store


@dataclass(frozen=True)
class FollowUpRule:
    code: str
    title: str
    keywords: tuple[str, ...]
    due_in_days: int
    instructions: tuple[str, ...]
    confidence: float = 0.9


FOLLOW_UP_RULES: tuple[FollowUpRule, ...] = (
    FollowUpRule(
        code="respiratory-infection",
        title="Tái khám hô hấp",
        keywords=("viêm phổi", "nhiễm trùng hô hấp", "ho đàm", "sốt"),
        due_in_days=3,
        instructions=("Đánh giá lại sốt và khó thở.", "Theo dõi đáp ứng kháng sinh nếu có."),
        confidence=0.93,
    ),
    FollowUpRule(
        code="cardiometabolic",
        title="Theo dõi tim mạch/chuyển hóa",
        keywords=("tăng huyết áp", "đái tháo đường", "suy tim"),
        due_in_days=14,
        instructions=("Theo dõi huyết áp/đường huyết theo kế hoạch.", "Đối chiếu thuốc đang dùng và triệu chứng mới."),
        confidence=0.88,
    ),
    FollowUpRule(
        code="post-procedure",
        title="Tái đánh giá sau thủ thuật",
        keywords=("sau mổ", "phẫu thuật", "thủ thuật"),
        due_in_days=7,
        instructions=("Kiểm tra vết mổ hoặc vị trí thủ thuật.", "Rà soát dấu hiệu nhiễm trùng hoặc đau tăng."),
        confidence=0.9,
    ),
    FollowUpRule(
        code="pain-followup",
        title="Đánh giá lại đau",
        keywords=("đau kéo dài", "đau tăng", "đau nhiều"),
        due_in_days=5,
        instructions=("Ghi nhận mức đau mỗi ngày.", "Quay lại sớm nếu đau tăng hoặc xuất hiện dấu hiệu mới."),
        confidence=0.84,
    ),
)


def _schedule_for(reference_date: date | None, due_in_days: int) -> date:
    base = reference_date or date.today()
    return base + timedelta(days=due_in_days)


def plan_follow_up(payload: FollowUpRequest, ctx: RequestContext) -> FollowUpPlanResponse:
    start = perf_counter()
    text = " ".join([payload.diagnosis_text, *payload.conditions, *payload.current_medications]).lower()
    suggestions: list[FollowUpSuggestion] = []

    for rule in FOLLOW_UP_RULES:
        if any(keyword in text for keyword in rule.keywords):
            suggestions.append(
                FollowUpSuggestion(
                    code=rule.code,
                    title=rule.title,
                    due_in_days=rule.due_in_days,
                    scheduled_for=_schedule_for(payload.discharge_date, rule.due_in_days),
                    instructions=list(rule.instructions),
                    basis="rule",
                    confidence=rule.confidence,
                )
            )

    for keyword, due_in_days in payload.customer_rules.items():
        if keyword.lower() in text:
            suggestions.append(
                FollowUpSuggestion(
                    code=f"customer::{keyword.lower()}",
                    title=f"Quy tắc khách hàng: {keyword}",
                    due_in_days=due_in_days,
                    scheduled_for=_schedule_for(payload.discharge_date, due_in_days),
                    instructions=["Áp dụng quy tắc riêng của khách hàng."],
                    basis="customer_rule",
                    confidence=0.8,
                )
            )

    suggestions = sorted(suggestions, key=lambda item: (item.due_in_days, item.code))
    status = Status.ok if suggestions else Status.unknown
    summary = (
        f"Tạo {len(suggestions)} mốc theo dõi."
        if suggestions
        else "Không có quy tắc phù hợp để sinh mốc tái khám."
    )
    response = FollowUpPlanResponse(
        request_id=ctx.request_id,
        status=status,
        plan_available=bool(suggestions),
        suggestions=suggestions,
        summary=summary,
        trace=Trace(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            rule_version="followup-rules@pha0",
            latency_ms=int((perf_counter() - start) * 1000),
            details={"matched_rules": [item.code for item in suggestions]},
        ),
    )
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="followup.plan",
            payload_type=payload.__class__.__name__,
            metadata={"plan_available": response.plan_available, "suggestion_count": len(suggestions)},
        )
    )
    return response
