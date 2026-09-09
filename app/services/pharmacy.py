from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from app.core.context import RequestContext
from app.models.common import Status, Trace
from app.models.pharmacy import FulfillmentRequest, PharmacyFulfillmentResponse, PharmacyOption
from app.services.audit import AuditEvent, audit_store


@dataclass(frozen=True)
class PharmacyBranch:
    code: str
    name: str
    modes: tuple[str, ...]
    location_keywords: tuple[str, ...]
    base_distance_km: float
    base_eta_minutes: int


PHARMACY_BRANCHES: tuple[PharmacyBranch, ...] = (
    PharmacyBranch(
        code="HCM-CENTRAL",
        name="Nhà thuốc Trung tâm HCM",
        modes=("pickup", "delivery"),
        location_keywords=("hcm", "tp hcm", "ho chi minh", "quan 1", "quận 1"),
        base_distance_km=2.2,
        base_eta_minutes=35,
    ),
    PharmacyBranch(
        code="HN-CENTRAL",
        name="Nhà thuốc Trung tâm Hà Nội",
        modes=("pickup", "delivery"),
        location_keywords=("hanoi", "ha noi", "hà nội", "quận hoàn kiếm"),
        base_distance_km=2.5,
        base_eta_minutes=40,
    ),
    PharmacyBranch(
        code="NATIONAL-EXPRESS",
        name="Nhà thuốc Giao Nhanh Quốc Gia",
        modes=("delivery",),
        location_keywords=(),
        base_distance_km=8.0,
        base_eta_minutes=75,
    ),
)


def _score_branch(branch: PharmacyBranch, location_text: str, preferred_mode: str, urgency: str) -> tuple[float, list[str], str]:
    rationale: list[str] = []
    score = 0.0
    if preferred_mode in branch.modes:
        score += 40
        rationale.append("preferred_mode_supported")
    else:
        score -= 20
        rationale.append("preferred_mode_mismatch")

    if any(keyword in location_text for keyword in branch.location_keywords):
        score += 35
        rationale.append("location_match")
    elif branch.location_keywords:
        score += 5
        rationale.append("generic_coverage")

    if urgency == "EMERGENCY" and "delivery" in branch.modes:
        score += 10
        rationale.append("urgent_delivery_bias")

    score += max(0.0, 20 - branch.base_distance_km * 2)
    score += max(0.0, 20 - branch.base_eta_minutes / 5)
    availability = "AVAILABLE" if score >= 50 else "LIMITED" if score >= 20 else "UNAVAILABLE"
    return score, rationale, availability


def plan_fulfillment(payload: FulfillmentRequest, ctx: RequestContext) -> PharmacyFulfillmentResponse:
    start = perf_counter()
    location_text = (payload.location_hint or "").lower()
    options = []
    for branch in PHARMACY_BRANCHES:
        score, rationale, availability = _score_branch(branch, location_text, payload.preferred_mode, payload.urgency)
        options.append(
            PharmacyOption(
                provider_code=branch.code,
                provider_name=branch.name,
                mode=payload.preferred_mode if payload.preferred_mode in branch.modes else branch.modes[0],
                availability=availability,
                eta_minutes=branch.base_eta_minutes,
                distance_km=branch.base_distance_km,
                confidence=round(min(0.98, max(0.35, score / 100)), 2),
                rationale=rationale,
            )
        )

    options.sort(key=lambda item: (-item.confidence, item.eta_minutes or 999, item.provider_code))
    needs_review = options[0].availability != "AVAILABLE" or any(not med.name.strip() for med in payload.medications)
    response = PharmacyFulfillmentResponse(
        request_id=ctx.request_id,
        status=Status.ok,
        needs_human_review=needs_review,
        recommended_mode=payload.preferred_mode,
        options=options,
        summary=(
            "Đã xếp các lựa chọn nhà thuốc theo mức phù hợp với vị trí và phương thức mong muốn."
            if options
            else "Không tìm được lựa chọn phù hợp."
        ),
        trace=Trace(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            rule_version="pharmacy-fulfillment@pha0",
            latency_ms=int((perf_counter() - start) * 1000),
            details={"option_count": len(options), "preferred_mode": payload.preferred_mode},
        ),
    )
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="pharmacy.fulfillment",
            payload_type=payload.__class__.__name__,
            metadata={"needs_human_review": response.needs_human_review, "top_option": options[0].provider_code},
        )
    )
    return response
