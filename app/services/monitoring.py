from __future__ import annotations

from collections import defaultdict
from time import perf_counter
from typing import Any

from app.core.context import RequestContext
from app.knowledge.loader import knowledge
from app.models.common import Status, Trace
from app.models.monitoring import (
    MonitoringAlert,
    MonitoringPoint,
    MonitoringRequest,
    MonitoringResponse,
    MonitoringTrend,
)
from app.services.audit import AuditEvent, audit_store


ESCALATION_ORDER = ("NONE", "SELF_CARE", "CLINIC", "URGENT", "EMERGENCY")
RULE_VERSION = "monitoring-rules@1.1.0+v28.1.0"


def _escalate(current: str, candidate: str) -> str:
    return max(current, candidate, key=ESCALATION_ORDER.index)


def _ordered_values(points: list[MonitoringPoint]) -> tuple[float, float]:
    ordered = sorted(points, key=lambda item: item.recorded_at)
    return ordered[0].value, ordered[-1].value


def _threshold_level(value: float, rule: dict[str, Any]) -> str | None:
    critical_above = rule.get("critical_above")
    critical_below = rule.get("critical_below")
    warning_above = rule.get("warning_above")
    warning_below = rule.get("warning_below")

    if critical_above is not None and value >= critical_above:
        return "critical"
    if critical_below is not None and value < critical_below:
        return "critical"
    if warning_above is not None and value >= warning_above:
        return "warning"
    if warning_below is not None and value < warning_below:
        return "warning"
    return None


def _trend_effect(direction: str, policy: str) -> str:
    if direction == "stable" or policy == "range_dependent":
        return "neutral"
    if policy == "higher_is_worse":
        return "worsening" if direction == "up" else "improving"
    if policy == "lower_is_worse":
        return "worsening" if direction == "down" else "improving"
    return "neutral"


def analyze_monitoring(payload: MonitoringRequest, ctx: RequestContext) -> MonitoringResponse:
    start = perf_counter()
    by_metric: dict[str, list[MonitoringPoint]] = defaultdict(list)
    for point in payload.metrics:
        by_metric[point.metric].append(point)

    rules = {rule["metric"]: rule for rule in knowledge.monitoring_rules}
    minimum_points = knowledge.monitoring_minimum_points
    alerts: list[MonitoringAlert] = []
    trends: list[MonitoringTrend] = []
    trend_effects: list[str] = []
    escalation = "NONE"

    for metric, points in by_metric.items():
        rule = rules.get(metric, {})
        ordered = sorted(points, key=lambda item: item.recorded_at)
        latest = ordered[-1].value

        threshold_level = _threshold_level(latest, rule)
        if threshold_level:
            candidate = rule.get(f"{threshold_level}_escalation", "CLINIC")
            escalation = _escalate(escalation, candidate)
            alerts.append(
                MonitoringAlert(
                    metric=metric,
                    severity="HIGH" if threshold_level == "critical" else "MODERATE",
                    detail=rule.get(f"detail_{threshold_level}", "Chỉ số vượt ngưỡng theo dõi."),
                    basis="threshold",
                    confidence=0.98 if threshold_level == "critical" else 0.95,
                )
            )

        if len(points) < minimum_points:
            trends.append(MonitoringTrend(metric=metric, direction="unknown", delta=None))
            continue

        first, last = _ordered_values(points)
        delta = round(last - first, 2)
        min_delta = float(rule.get("trend_min_delta", 0.1))
        direction = "stable" if abs(delta) < min_delta else ("up" if delta > 0 else "down")
        trends.append(MonitoringTrend(metric=metric, direction=direction, delta=delta))
        effect = _trend_effect(direction, rule.get("trend_policy", "range_dependent"))
        if effect != "neutral":
            trend_effects.append(effect)

    has_trend_data = any(trend.direction != "unknown" for trend in trends)
    if alerts:
        overall = "worsening"
        status = Status.ok
    elif not has_trend_data:
        overall = "insufficient_data"
        status = Status.unknown
        alerts.append(
            MonitoringAlert(
                metric="overall",
                severity="LOW",
                detail=f"Cần ít nhất {minimum_points} điểm cho cùng một chỉ số để phân tích xu hướng.",
                basis="insufficient_data",
                confidence=1.0,
            )
        )
    elif "worsening" in trend_effects:
        overall = "worsening"
        status = Status.ok
        escalation = _escalate(escalation, "CLINIC")
        for trend in trends:
            rule = rules.get(trend.metric, {})
            if _trend_effect(trend.direction, rule.get("trend_policy", "range_dependent")) == "worsening":
                alerts.append(
                    MonitoringAlert(
                        metric=trend.metric,
                        severity="MODERATE",
                        detail="Xu hướng chỉ số đang diễn tiến theo hướng bất lợi và cần được đánh giá.",
                        basis="trend",
                        confidence=0.85,
                    )
                )
    elif trend_effects and all(effect == "improving" for effect in trend_effects):
        overall = "improving"
        status = Status.ok
    else:
        overall = "stable"
        status = Status.ok

    response = MonitoringResponse(
        request_id=ctx.request_id,
        status=status,
        trend=overall,
        escalation_level=escalation,
        alerts=alerts,
        metrics=trends,
        summary=f"Phân tích {len(payload.metrics)} điểm theo dõi trên {len(by_metric)} loại chỉ số.",
        trace=Trace(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            rule_version=RULE_VERSION,
            knowledge_version=knowledge.version_string(),
            latency_ms=int((perf_counter() - start) * 1000),
            details={
                "point_count": len(payload.metrics),
                "metric_count": len(by_metric),
                "minimum_points_per_metric": minimum_points,
                "knowledge_integrity": knowledge.integrity_report(),
            },
        ),
    )

    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="monitoring.ingest",
            payload_type=payload.__class__.__name__,
            metadata={
                "trend": response.trend,
                "escalation_level": response.escalation_level,
                "rule_version": RULE_VERSION,
            },
        )
    )
    return response
