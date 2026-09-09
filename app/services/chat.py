"""Deterministic natural-language orchestration over clinical domain services."""

from __future__ import annotations

from datetime import date, datetime, time as datetime_time, timedelta, timezone
from hashlib import sha256
import re
from typing import Any
from zoneinfo import ZoneInfo

from app.core.context import RequestContext
from app.knowledge.loader import knowledge
from app.models.chat import ChatIntent, ChatRequest, ChatResponse, ChatSuggestion
from app.models.delivery import DeliveryRequest
from app.models.followup import FollowUpRequest
from app.models.monitoring import MonitoringPoint, MonitoringRequest
from app.models.pharmacy import FulfillmentMedication, FulfillmentRequest
from app.models.product import ProductVerificationRequest
from app.models.queue import QueueItem, QueuePrioritizeRequest
from app.models.safety import Allergy, MedicationItem, SafetyRequest
from app.models.schedule import MedicationScheduleCreate
from app.models.triage import TriageRequest, VitalSigns
from app.services.answering import build_grounded_answer
from app.services.answer_agents import answer_agent_pipeline
from app.services.audit import AuditEvent, audit_store
from app.services.chat_history import chat_history_store
from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text
from app.services.delivery import prepare_delivery
from app.services.fhir import to_fhir_bundle, to_fhir_risk_assessment
from app.services.followup import plan_follow_up
from app.services.monitoring import analyze_monitoring
from app.services.pharmacy import plan_fulfillment
from app.services.product_verification import verify_product_code
from app.services.queue import prioritize_queue
from app.services.safety import evaluate_safety
from app.services.schedules import medication_schedule_store
from app.services.triage import evaluate_triage


_INTENT_KEYWORDS: dict[ChatIntent, tuple[str, ...]] = {
    "triage": (
        "phan luong",
        "trieu chung",
        "cap cuu",
        "dau nguc",
        "tuc nguc",
        "nang nguc",
        "dau that nguc",
        "kho chiu o nguc",
        "dau vung tim",
        "dau lan tay",
        "dau lan vai",
        "dau lan ham",
        "kho tho",
        "tho gap",
        "tho doc",
        "tho khok khe",
        "hut hoi",
        "tim dap nhanh",
        "danh trong nguc",
        "hoi hop",
        "meo mieng",
        "yeu liet",
        "te bi",
        "te nua nguoi",
        "kho noi",
        "noi ngong",
        "ngat",
        "ngat xiu",
        "hon me",
        "co giat",
        "dau dau",
        "dau nua dau",
        "dau bung",
        "dau bung du doi",
        "con cao",
        "nong rat bung",
        "kho chiu o bung",
        "chong mat",
        "hoa mat",
        "choang vang",
        "buon non",
        "non mua",
        "tieu chay",
        "phat ban",
        "noi man",
        "ngua",
        "met moi",
        "sot",
        "sot cao",
        "lanh run",
        "ho",
        "ho ra mau",
        "ho dam",
    ),
    "safety": (
        "tuong tac thuoc",
        "an toan thuoc",
        "di ung",
        "chong chi dinh",
        "phoi hop thuoc",
        "ke don",
        "ke lieu",
        "lieu dung",
    ),
    "monitoring": ("theo doi", "spo2", "huyet ap", "nhip tim", "nhiet do", "duong huyet"),
    "followup": (
        "tai kham",
        "follow up",
        "follow-up",
        "lich kham",
        "sau xuat vien",
        "ca kham",
        "ca truc",
        "lich bac si",
        "dat ca kham",
        "ca sang",
        "ca chieu",
        "ca toi",
        "lich hen",
        "dat lich",
    ),
    "pharmacy": ("nha thuoc", "cap phat", "tim thuoc", "giao thuoc", "nhan tai quay"),
    "queue": ("hang doi", "xep hang", "thu tu tiep nhan", "uu tien benh nhan"),
    "fhir": ("fhir", "bundle", "xuat ho so"),
    "delivery": ("webhook", "gui ket qua", "delivery", "notification", "sse"),
    "ocr": ("ocr", "doc don thuoc", "anh don thuoc", "quet don thuoc"),
    "schedule": ("lich uong thuoc", "nhac uong", "dat lich uong", "#lichthuoc", "hen gio uong"),
    "authenticity": ("hang gia", "hang nhai", "chinh hang", "quet qr", "kiem tra qr", "xac thuc thuoc"),
}

_RESEARCH_AGENT_INTENTS: set[ChatIntent] = {
    "triage",
    "safety",
    "monitoring",
    "followup",
    "pharmacy",
    "authenticity",
}

_SYMPTOM_FALLBACK_MARKERS = (
    "dau",
    "nhuc",
    "tuc",
    "nang",
    "nguc",
    "tim",
    "tho",
    "kho tho",
    "sot",
    "ho",
    "te",
    "sung",
    "ngua",
    "non",
    "met",
    "choang",
    "ngat",
    "kho chiu",
    "hoi hop",
    "chay mau",
    "noi man",
    "phat ban",
    "tieu chay",
    "tao bon",
    "co giat",
    "chuot rut",
    "yeu liet",
    "nong rat",
    "lanh run",
    "nhoi",
    "con cao",
)

_NEW_CLINICAL_EPISODE_MARKERS = (
    "yeu cau moi",
    "trieu chung moi",
    "van de moi",
    "chuyen khac",
    "khong lien quan",
)

_TRIAGE_CONTINUATION_MARKERS = (
    "cam giac no",
    "no cu",
    "van con",
    "van bi",
    "them",
    "nang hon",
    "te hon",
    "do hon",
    "buon non",
    "non them",
    "dau tang",
    "kho chiu lam",
)


def _normalize(value: str) -> str:
    return normalize_search_text(value)


def _triage_episode_text(payload: ChatRequest, latest_text: str) -> tuple[str, bool]:
    """Carry one explicit continuation turn without reviving a closed episode."""
    normalized_latest = _normalize(latest_text)
    if any(marker in normalized_latest for marker in _NEW_CLINICAL_EPISODE_MARKERS):
        return latest_text, False
    if not any(marker in normalized_latest for marker in _TRIAGE_CONTINUATION_MARKERS):
        return latest_text, False

    previous_user = next(
        (
            message.content.strip()
            for message in reversed(payload.messages[:-1])
            if message.role == "user" and message.content.strip()
        ),
        None,
    )
    if previous_user is None:
        return latest_text, False
    normalized_previous = _normalize(previous_user)
    if not any(marker in normalized_previous for marker in _SYMPTOM_FALLBACK_MARKERS):
        return latest_text, False
    return f"{previous_user[:2000]}\nCập nhật hiện tại: {latest_text}", True


def _requests_personalized_dose(normalized_text: str) -> bool:
    return bool(
        re.search(r"\bke(?:\s+[a-z0-9_-]+){0,4}\s+lieu\b", normalized_text)
        or "lieu chinh xac" in normalized_text
        or "tu dieu chinh lieu" in normalized_text
    )


def _detect_intent(payload: ChatRequest, normalized_text: str) -> ChatIntent:
    if payload.intent_hint != "auto":
        return payload.intent_hint

    def contains(keyword: str) -> bool:
        if " " not in keyword and len(keyword) <= 3:
            return any(
                contains_affirmed_phrase(normalized_text, match.group(0))
                for match in re.finditer(
                    rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])",
                    normalized_text,
                )
            )
        return contains_affirmed_phrase(normalized_text, keyword)

    scores = {
        intent: sum(2 if contains(keyword) else 0 for keyword in keywords)
        for intent, keywords in _INTENT_KEYWORDS.items()
    }
    if re.search(r"\b(spo2|huyet ap|nhip tim|nhiet do)\s*[:=]?\s*\d", normalized_text):
        scores["monitoring"] += 4
    if _requests_personalized_dose(normalized_text):
        scores["safety"] += 6
    if re.search(r"\bnhac(?:\s+[a-z0-9_-]+){0,3}\s+uong\b", normalized_text) or (
        "uong" in normalized_text
        and re.search(r"(?<!\d)(?:[01]?\d|2[0-3])(?:h(?:\d{2})?|:\d{2})(?!\d)", normalized_text)
    ):
        scores["schedule"] += 6

    # Direct match against clinical emergency keywords & knowledge red flag patterns
    if any(contains_affirmed_phrase(normalized_text, term) for term in (
        "dau nguc", "tuc nguc", "nang nguc", "dau that nguc", "kho tho", "meo mieng",
        "ngat", "dot quy", "nhoi mau", "tim dap nhanh", "danh trong nguc", "yeu liet",
        "hon me", "co giat"
    )):
        scores["triage"] += 10

    for rf in knowledge.red_flag_patterns + knowledge.urgent_patterns:
        if any(
            contains_affirmed_phrase(normalized_text, _normalize(p))
            for p in (*rf.get("patterns_vi", []), *rf.get("patterns_en", []))
        ):
            scores["triage"] += 10
            break

    intent, score = max(scores.items(), key=lambda item: item[1])
    if score:
        return intent
    if any(contains(marker) for marker in _SYMPTOM_FALLBACK_MARKERS):
        return "triage"
    if "thuoc" in normalized_text and any(
        marker in normalized_text for marker in ("uong", "dung", "lieu", "tac dung", "phan ung")
    ):
        return "safety"
    return "general"


def _patient_ref(payload: ChatRequest, text: str) -> str | None:
    direct = re.search(r"\b(?:BN|HS|PATIENT|P)[-_][A-Z0-9][A-Z0-9._-]*\b", text.upper())
    if direct:
        return direct.group(0)
    labeled = re.search(
        r"(?:bệnh nhân|mã hồ sơ|patient)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9._-]{1,127})",
        text,
        re.IGNORECASE,
    )
    if labeled:
        return labeled.group(1)
    return payload.context.patient_ref.strip() if payload.context.patient_ref and payload.context.patient_ref.strip() else None


def _known_medications() -> dict[str, str]:
    values: set[str] = set()
    for interaction in knowledge.drug_interactions:
        values.update(str(item) for item in interaction.get("pair", []))
    for group in knowledge.allergy_groups:
        values.add(str(group.get("primary_allergen", "")))
        values.update(str(item) for item in group.get("cross_reactive_substances", []))
        values.update(str(item) for item in group.get("partial_cross_reactive", []))
    for contraindication in knowledge.contraindications:
        values.update(str(item) for item in contraindication.get("medications", []))
    return {_normalize(value): value.lower() for value in values if value}


_MEDICATIONS = _known_medications()


def _medication_occurrences(normalized_text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for normalized, canonical in sorted(_MEDICATIONS.items(), key=lambda item: -len(item[0])):
        match = re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", normalized_text)
        if match:
            found.append((match.start(), canonical))
    return sorted(found)


def _first_marker(text: str, markers: tuple[str, ...]) -> int | None:
    positions = [text.find(marker) for marker in markers if marker in text]
    return min(positions) if positions else None


def _extract_safety(payload: ChatRequest, normalized_text: str) -> tuple[list[str], list[str], list[str], list[str]]:
    occurrences = _medication_occurrences(normalized_text)
    current_marker = _first_marker(normalized_text, ("dang dung", "hien dung", "thuoc hien tai"))
    proposed_marker = _first_marker(normalized_text, ("du dinh", "muon dung", "de xuat", "them thuoc", "phoi hop voi"))
    allergy_marker = _first_marker(normalized_text, ("di ung", "phan ung voi"))

    current = [name.lower() for name in payload.context.current_medications]
    proposed: list[str] = []
    allergens = [name.lower() for name in payload.context.allergies]

    for position, medication in occurrences:
        if allergy_marker is not None and allergy_marker < position < allergy_marker + 45:
            allergens.append(medication)
        elif proposed_marker is not None and position > proposed_marker:
            proposed.append(medication)
        elif current_marker is not None and position > current_marker:
            current.append(medication)

    if not current and not proposed and len(occurrences) >= 2:
        current = [occurrences[0][1]]
        proposed = [name for _, name in occurrences[1:]]
    elif not proposed and allergens:
        proposed = [name for position, name in occurrences if name not in allergens and (allergy_marker is None or position > allergy_marker)]

    conditions = [condition.lower() for condition in payload.context.conditions]
    for rule in knowledge.contraindications:
        for condition in rule.get("conditions", []):
            if _normalize(str(condition)) in normalized_text:
                conditions.append(str(condition).lower())

    return (
        list(dict.fromkeys(current)),
        list(dict.fromkeys(proposed)),
        list(dict.fromkeys(allergens)),
        list(dict.fromkeys(conditions)),
    )


def _extract_monitoring(text: str) -> list[MonitoringPoint]:
    normalized = _normalize(text).replace(",", ".")
    recorded_at = datetime.now(timezone.utc)
    points: list[MonitoringPoint] = []
    patterns = (
        ("spo2", r"\bspo2\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)", "%"),
        ("heart_rate", r"(?:nhip tim|mach)\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)", "bpm"),
        ("temperature_c", r"(?:nhiet do|sot)\s*[:=]?\s*(\d{2}(?:\.\d+)?)", "C"),
        ("glucose_mg_dl", r"(?:duong huyet|glucose)\s*[:=]?\s*(\d{2,4}(?:\.\d+)?)", "mg/dl"),
        ("pain_score", r"(?:muc dau|dau)\s*[:=]?\s*(\d{1,2}(?:\.\d+)?)\s*/\s*10", "/10"),
    )
    for metric, pattern, unit in patterns:
        match = re.search(pattern, normalized)
        if match:
            points.append(MonitoringPoint(metric=metric, value=float(match.group(1)), unit=unit, recorded_at=recorded_at))
    pressure = re.search(r"(?:huyet ap|ha)\s*[:=]?\s*(\d{2,3})\s*/\s*(\d{2,3})", normalized)
    if pressure:
        points.extend(
            [
                MonitoringPoint(metric="systolic", value=float(pressure.group(1)), unit="mmHg", recorded_at=recorded_at),
                MonitoringPoint(metric="diastolic", value=float(pressure.group(2)), unit="mmHg", recorded_at=recorded_at),
            ]
        )
    return points


def _extract_vital_signs(text: str) -> VitalSigns | None:
    values = {point.metric: point.value for point in _extract_monitoring(text)}
    supported = {key: values[key] for key in ("systolic", "diastolic", "heart_rate", "temperature_c", "spo2") if key in values}
    if not supported:
        return None
    return VitalSigns(
        systolic=int(supported["systolic"]) if "systolic" in supported else None,
        diastolic=int(supported["diastolic"]) if "diastolic" in supported else None,
        heart_rate=int(supported["heart_rate"]) if "heart_rate" in supported else None,
        temperature_c=supported.get("temperature_c"),
        spo2=int(supported["spo2"]) if "spo2" in supported else None,
    )


def _extract_queue(text: str) -> list[QueueItem]:
    items: list[QueueItem] = []
    for segment in re.split(r"[;\n]+", text):
        patient = re.search(r"\b(?:BN|HS|PATIENT|P)[-_][A-Z0-9][A-Z0-9._-]*\b", segment.upper())
        if not patient:
            continue
        normalized = _normalize(segment)
        urgency = "EMERGENCY" if "emergency" in normalized or "cap cuu" in normalized else "URGENT" if "urgent" in normalized or "khan" in normalized else "ROUTINE"
        esi_match = re.search(r"\besi\s*[:=]?\s*([1-5])", normalized)
        wait_match = re.search(r"(?:cho|wait)\s*[:=]?\s*(\d+)", normalized)
        items.append(
            QueueItem(
                patient_ref=patient.group(0),
                urgency=urgency,
                emergency_flag=urgency == "EMERGENCY",
                esi_level=int(esi_match.group(1)) if esi_match else None,
                wait_minutes=int(wait_match.group(1)) if wait_match else 0,
            )
        )
    return items


def _extract_schedule(text: str) -> tuple[str | None, list[datetime], str]:
    normalized = _normalize(text)
    occurrences = _medication_occurrences(normalized)
    medication = occurrences[0][1] if occurrences else None
    if medication is None:
        match = re.search(
            r"(?:thuoc|uong)\s+([a-z][a-z0-9 ._-]{1,80}?)(?=\s+(?:luc|vao|ngay|moi ngay|hang ngay)|[,;]|$)",
            normalized,
        )
        medication = match.group(1).strip() if match else None

    raw_times = re.findall(r"(?<!\d)([01]?\d|2[0-3])(?:h(?:(\d{2}))?|:(\d{2}))(?!\d)", normalized)
    times: list[datetime_time] = []
    for hour, h_minutes, colon_minutes in raw_times:
        minute = int(h_minutes or colon_minutes or 0)
        if minute > 59:
            continue
        candidate = datetime_time(hour=int(hour), minute=minute)
        if candidate not in times:
            times.append(candidate)

    local_zone = ZoneInfo("Asia/Ho_Chi_Minh")
    now = datetime.now(local_zone)
    target_date = now.date()
    if "ngay mai" in normalized:
        target_date += timedelta(days=1)
    else:
        iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", normalized)
        local_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(20\d{2}))?\b", normalized)
        try:
            if iso_match:
                target_date = date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
            elif local_match:
                target_date = date(
                    int(local_match.group(3) or now.year),
                    int(local_match.group(2)),
                    int(local_match.group(1)),
                )
        except ValueError:
            return medication, [], "once"

    recurrence = "daily" if any(marker in normalized for marker in ("moi ngay", "hang ngay", "hang ngay", "mỗi ngày")) else "once"
    scheduled: list[datetime] = []
    for value in times:
        candidate = datetime.combine(target_date, value, tzinfo=local_zone)
        if recurrence == "daily" and candidate <= now:
            candidate += timedelta(days=1)
        scheduled.append(candidate)
    return medication, scheduled, recurrence


def _suggestions(intent: ChatIntent) -> list[ChatSuggestion]:
    common = {
        "triage": ChatSuggestion(label="Thêm dấu hiệu sinh tồn", prompt="SpO2 94%, huyết áp 150/90, nhịp tim 105", intent="monitoring"),
        "safety": ChatSuggestion(label="Theo dõi chỉ số", prompt="Theo dõi SpO2 97%, nhịp tim 82", intent="monitoring"),
        "monitoring": ChatSuggestion(label="Lập kế hoạch tái khám", prompt="Lập lịch tái khám sau xuất viện", intent="followup"),
    }
    values = [common[intent]] if intent in common else []
    if intent == "schedule":
        values.append(ChatSuggestion(label="Xem lịch uống thuốc", prompt="Hiển thị lịch uống thuốc", intent="schedule"))
    if intent in ("triage", "followup"):
        values.append(ChatSuggestion(label="Xem lịch ca khám", prompt="Xem lịch ca khám và bác sĩ hôm nay", intent="followup"))
    values.append(ChatSuggestion(label="Xuất FHIR", prompt="Xuất kết quả này sang FHIR", intent="fhir"))
    return values


def _response(
    payload: ChatRequest,
    ctx: RequestContext,
    *,
    status: str,
    intent: ChatIntent,
    reply: str,
    required_fields: list[str] | None = None,
    extracted: dict[str, Any] | None = None,
    result: Any | None = None,
    agent_question: str | None = None,
) -> ChatResponse:
    serialized = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    fields = required_fields or []
    answer = build_grounded_answer(
        intent=intent,
        status=status,
        reply=reply,
        required_fields=fields,
        result=serialized,
    )
    if status == "answered" and intent in _RESEARCH_AGENT_INTENTS:
        answer = answer_agent_pipeline.enhance(
            answer=answer,
            intent=intent,
            question=agent_question or payload.messages[-1].content,
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            conversation_id=payload.conversation_id,
            locale=payload.locale,
            patient_context=payload.context.model_dump(mode="json"),
        )
    internal_agent_trace = answer.agent_trace
    agent_status = internal_agent_trace.status if internal_agent_trace else None
    orchestrator = {
        "verified": "agent_verified",
        "shadow": "agent_shadow",
        "unavailable": "deterministic_fallback",
        "rejected": "deterministic_fallback",
        "error": "deterministic_fallback",
        "circuit_open": "deterministic_fallback",
    }.get(agent_status, "deterministic")
    answer = answer.model_copy(update={"agent_trace": None})
    response = ChatResponse(
        request_id=ctx.request_id,
        conversation_id=payload.conversation_id,
        status=status,
        intent=intent,
        reply=answer.summary,
        required_fields=fields,
        extracted=extracted or {},
        result=serialized,
        answer=answer,
        suggestions=_suggestions(intent) if status == "answered" else [],
        orchestrator=orchestrator,  # type: ignore[arg-type]
    )
    chat_history_store.append_exchange(ctx.tenant_id, payload, response)
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="chat.route",
            payload_type="ChatRequest",
            metadata={
                "intent": intent,
                "status": status,
                "conversation_id": payload.conversation_id,
                "answer_assurance": "source_verified" if agent_status == "verified" else "baseline",
            },
        )
    )
    return response


def orchestrate_chat(payload: ChatRequest, ctx: RequestContext) -> ChatResponse:
    latest_text = payload.messages[-1].content
    normalized = _normalize(latest_text)
    intent = _detect_intent(payload, normalized)
    patient_ref = _patient_ref(payload, latest_text)

    if intent == "authenticity":
        latest = payload.messages[-1].content
        raw_match = re.search(r"MEDGUARD\|[^\s]+", latest, re.IGNORECASE)
        if not raw_match:
            return _response(
                payload,
                ctx,
                status="needs_information",
                intent=intent,
                reply="Hãy quét QR trên bao bì hoặc gửi nguyên nội dung mã để đối chiếu registry.",
                required_fields=["qr_payload"],
            )
        result = verify_product_code(ProductVerificationRequest(raw_code=raw_match.group(0)), ctx)
        return _response(
            payload,
            ctx,
            status="answered",
            intent=intent,
            reply=f"Đã đối chiếu mã sản phẩm. Trạng thái: {result.verification_status}.",
            extracted={"verification_status": result.verification_status},
            result=result,
        )

    if intent == "general":
        return _response(
            payload,
            ctx,
            status="needs_information",
            intent=intent,
            reply="Mình là Trợ lý MedGuard AI. Bạn hãy chia sẻ cụ thể hơn về triệu chứng, vị trí khó chịu, đơn thuốc hoặc chỉ số sức khỏe để hệ thống chọn đúng nghiệp vụ và đưa ra hướng dẫn phù hợp.",
            required_fields=["request_detail"],
        )

    if intent == "ocr":
        return _response(payload, ctx, status="needs_information", intent=intent, reply="Hãy đính kèm ảnh đơn thuốc và chọn hồ sơ bệnh nhân.", required_fields=["prescription_image", "patient_ref"])

    if intent == "schedule":
        medication, scheduled_times, recurrence = _extract_schedule(latest_text)
        required_fields = []
        if not patient_ref:
            required_fields.append("patient_ref")
        if not medication:
            required_fields.append("medication_name")
        if not scheduled_times:
            required_fields.append("scheduled_at")
        if required_fields:
            return _response(
                payload,
                ctx,
                status="needs_information",
                intent=intent,
                reply="Hãy cho biết tên thuốc và giờ uống, ví dụ: #lichthuoc BN-001 uống amoxicillin lúc 8h và 20h mỗi ngày.",
                required_fields=required_fields,
                extracted={"patient_ref": patient_ref, "medication_name": medication},
            )
        schedules = [
            medication_schedule_store.create(
                ctx.tenant_id,
                MedicationScheduleCreate(
                    patient_ref=patient_ref or "",
                    medication_name=medication or "",
                    scheduled_at=scheduled_at,
                    recurrence=recurrence,
                    source="chat",
                ),
            )
            for scheduled_at in scheduled_times
        ]
        return _response(
            payload,
            ctx,
            status="answered",
            intent=intent,
            reply=f"Đã thêm {len(schedules)} mốc uống {medication} vào lịch của {patient_ref}.",
            extracted={"patient_ref": patient_ref, "medication_name": medication, "recurrence": recurrence},
            result={"schedules": [item.model_dump(mode="json") for item in schedules]},
        )

    execution_patient_ref = patient_ref or (
        "CHAT-" + sha256(f"{ctx.tenant_id}:{payload.conversation_id}".encode("utf-8")).hexdigest()[:16].upper()
    )

    if intent == "triage":
        episode_text, episode_context_used = _triage_episode_text(payload, latest_text)
        vital_signs = _extract_vital_signs(episode_text)
        result = evaluate_triage(
            TriageRequest(
                patient_ref=execution_patient_ref,
                symptoms_text=episode_text,
                age=payload.context.age,
                sex=payload.context.sex,
                known_conditions=payload.context.conditions,
                current_medications=[
                    {"name": name, "active_ingredient": name}
                    for name in payload.context.current_medications
                ],
                vitals=vital_signs,
            ),
            ctx,
        )
        specialty = result.recommended_specialty.label if result.recommended_specialty else "chuyên khoa phù hợp"
        return _response(
            payload,
            ctx,
            status="answered",
            intent=intent,
            reply=f"Đã phân luồng ở mức {result.urgency}, ESI {result.esi_level or 'chưa xác định'}. Hướng xử lý: {specialty}.",
            extracted={
                "patient_ref": patient_ref,
                "vital_signs": vital_signs.model_dump(mode="json") if vital_signs else None,
                "episode_context_used": episode_context_used,
            },
            result=result,
            agent_question=episode_text,
        )

    if intent == "safety":
        if _requests_personalized_dose(normalized):
            return _response(
                payload,
                ctx,
                status="unsupported",
                intent=intent,
                reply=(
                    "MedGuard không kê hoặc tính liều thuốc cá nhân hóa từ hội thoại. "
                    "Liều dùng cần được bác sĩ hoặc dược sĩ xác nhận dựa trên chỉ định, "
                    "xét nghiệm, bệnh nền và các thuốc đang sử dụng."
                ),
            )
        current, proposed, allergens, conditions = _extract_safety(payload, normalized)
        if not proposed:
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Tôi cần tên thuốc đang cân nhắc hoặc thuốc muốn phối hợp để kiểm tra.", required_fields=["proposed_medications"], extracted={"current_medications": current, "allergies": allergens})
        result = evaluate_safety(
            SafetyRequest(
                patient_ref=execution_patient_ref,
                age=payload.context.age,
                sex=payload.context.sex,
                current_medications=[MedicationItem(name=name, active_ingredient=name) for name in current],
                proposed_medications=[MedicationItem(name=name, active_ingredient=name) for name in proposed],
                allergies=[Allergy(substance=name) for name in allergens],
                conditions=conditions,
            ),
            ctx,
        )
        return _response(payload, ctx, status="answered", intent=intent, reply=f"Đã kiểm tra an toàn thuốc. Mức nguy cơ tổng thể là {result.overall_risk}; {'cần' if result.requires_human_review else 'chưa cần'} người có thẩm quyền rà soát.", extracted={"patient_ref": patient_ref, "current_medications": current, "proposed_medications": proposed, "allergies": allergens, "conditions": conditions}, result=result)

    if intent == "monitoring":
        points = _extract_monitoring(latest_text)
        if not points:
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Hãy gửi ít nhất một chỉ số kèm giá trị, ví dụ SpO2 94%, huyết áp 150/90 hoặc nhiệt độ 38.5°C.", required_fields=["monitoring_metric"])
        result = analyze_monitoring(MonitoringRequest(patient_ref=execution_patient_ref, metrics=points), ctx)
        return _response(payload, ctx, status="answered", intent=intent, reply=f"Đã đọc {len(points)} chỉ số. Mức escalation hiện tại là {result.escalation_level} và xu hướng là {result.trend}.", extracted={"patient_ref": patient_ref, "metrics": [point.model_dump(mode="json") for point in points]}, result=result)

    if intent == "followup":
        result = plan_follow_up(FollowUpRequest(patient_ref=execution_patient_ref, diagnosis_text=latest_text, conditions=payload.context.conditions, current_medications=payload.context.current_medications), ctx)
        return _response(payload, ctx, status="answered", intent=intent, reply=result.summary, extracted={"patient_ref": patient_ref}, result=result)

    if intent == "pharmacy":
        medications = [name for _, name in _medication_occurrences(normalized)]
        if not medications:
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Hãy cho biết tên thuốc cần tìm hoặc cấp phát.", required_fields=["medications"])
        mode = "delivery" if "giao" in normalized else "pickup"
        urgency = "EMERGENCY" if "cap cuu" in normalized else "URGENT" if "khan" in normalized else "ROUTINE"
        result = plan_fulfillment(FulfillmentRequest(patient_ref=execution_patient_ref, medications=[FulfillmentMedication(name=name, active_ingredient=name, quantity=1) for name in medications], preferred_mode=mode, urgency=urgency), ctx)
        return _response(payload, ctx, status="answered", intent=intent, reply=result.summary, extracted={"patient_ref": patient_ref, "medications": medications, "preferred_mode": mode}, result=result)

    if intent == "queue":
        items = _extract_queue(latest_text)
        if not items:
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Gửi mỗi bệnh nhân trên một dòng, gồm mã hồ sơ, mức ROUTINE/URGENT/EMERGENCY, ESI và số phút chờ.", required_fields=["queue_items"])
        result = prioritize_queue(QueuePrioritizeRequest(items=items), ctx)
        return _response(payload, ctx, status="answered", intent=intent, reply=f"Đã xếp thứ tự {len(items)} bệnh nhân. Hồ sơ ưu tiên đầu tiên là {result.items[0].patient_ref}.", extracted={"item_count": len(items)}, result=result)

    if intent == "fhir":
        last = payload.context.last_result or {}
        if not last or not patient_ref:
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Cần một kết quả lâm sàng trước đó và mã hồ sơ để tạo FHIR Bundle.", required_fields=["last_result", "patient_ref"])
        resources: list[dict[str, Any]] = []
        if "urgency" in last:
            resources.append(to_fhir_risk_assessment(patient_ref=patient_ref, esi_level=last.get("esi_level"), urgency=last.get("urgency", "ROUTINE"), red_flags=last.get("red_flags", []), specialty=(last.get("recommended_specialty") or {}).get("code")))
        bundle = to_fhir_bundle(resources)
        return _response(payload, ctx, status="answered", intent=intent, reply=f"Đã tạo FHIR R4 Bundle gồm {bundle['total']} tài nguyên từ kết quả gần nhất.", extracted={"patient_ref": patient_ref}, result=bundle)

    if intent == "delivery":
        last = payload.context.last_result
        if not last:
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Cần một kết quả trước đó để chuẩn bị gói chuyển tiếp.", required_fields=["last_result"])
        channel = "sse" if "sse" in normalized else "notification" if "notification" in normalized or "thong bao" in normalized else "webhook"
        result = prepare_delivery(DeliveryRequest(event_name="clinical.result.ready", channel=channel, body=last), ctx)
        return _response(payload, ctx, status="answered", intent=intent, reply=result.summary, extracted={"channel": channel}, result=result)

    return _response(payload, ctx, status="unsupported", intent=intent, reply="Yêu cầu này chưa có bộ xử lý an toàn phù hợp.")
