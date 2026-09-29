"""Natural-language medication schedule commands with persistent CRUD semantics.

V25.6 keeps schedule operations separate from clinical triage. Phrases such as
"uống thuốc" inside an explicit reminder/card command are workflow instructions,
not evidence that a medication was already ingested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time as datetime_time, timedelta
import re
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.models.schedule import MedicationScheduleCreate, MedicationScheduleUpdate
from app.services.clinical_text import normalize_search_text
from app.services.schedules import MedicationScheduleStore, medication_schedule_store


ScheduleAction = Literal["create", "view", "update", "cancel", "delete"]


@dataclass(frozen=True)
class ScheduleCommandResult:
    status: Literal["answered", "needs_information"]
    reply: str
    required_fields: list[str] = field(default_factory=list)
    extracted: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None


_VIEW_MARKERS = (
    "xem lai card",
    "xem card",
    "hien thi card",
    "xem lai lich uong",
    "hien thi lich uong",
)
_UPDATE_MARKERS = ("doi gio", "cap nhat gio", "sua gio", "chuyen gio")
_DELETE_MARKERS = ("xoa card", "xoa lich nhac", "xoa lich uong", "xoa nhac")
_CANCEL_MARKERS = (
    "huy card",
    "tam dung card",
    "ngung card",
    "huy lich nhac",
    "tam dung lich",
    "huy nhac",
    "tam dung nhac",
)
_CREATE_MARKERS = (
    "#lichthuoc",
    "tao card",
    "tao cho toi mot card",
    "dat card",
    "card lich uong",
    "card lich thuoc",
    "card nhac",
    "lich uong thuoc",
    "nhac toi uong",
    "nhac uong",
    "hen gio uong",
)


def is_schedule_chat_command(text: str) -> bool:
    """Recognize explicit medication-card workflow language before triage routing."""
    normalized = normalize_search_text(text)
    if any(
        marker in normalized
        for marker in (
            *_VIEW_MARKERS,
            *_UPDATE_MARKERS,
            *_DELETE_MARKERS,
            *_CANCEL_MARKERS,
            *_CREATE_MARKERS,
        )
    ):
        return True
    return bool(
        "card" in normalized
        and any(word in normalized for word in ("uong", "thuoc", "nhac", "gio"))
    )


def _action(text: str) -> ScheduleAction:
    normalized = normalize_search_text(text)
    if any(marker in normalized for marker in _DELETE_MARKERS):
        return "delete"
    if any(marker in normalized for marker in _CANCEL_MARKERS):
        return "cancel"
    if any(marker in normalized for marker in _UPDATE_MARKERS):
        return "update"
    if any(marker in normalized for marker in _VIEW_MARKERS):
        return "view"
    return "create"


def _extract_medication(text: str) -> str | None:
    """Extract the medication name while discarding schedule-command scaffolding.

    Command nouns such as ``card nhắc`` or ``lịch uống`` are intentionally
    consumed by the regex rather than becoming part of the medicine name. This
    keeps create/view/update/cancel/delete references stable across follow-up
    wording variants.
    """
    normalized = normalize_search_text(text)
    stop = (
        r"(?=\s+(?:moi\s+ngay|hang\s+ngay|luc|vao|tu\s+\d|sang\s+\d|"
        r"do\b|nay\b|vua\b|giup\s+toi|thoi\b|hien\s+tai\b|tu\s+hom\s+nay\b)|[,.!?;]|$)"
    )
    patterns = (
        rf"\bthuoc\s+([a-z][a-z0-9+._ -]{{1,80}}?){stop}",
        rf"\bcard(?:\s+(?:lich\s+uong(?:\s+thuoc)?|lich\s+thuoc|nhac(?:\s+toi)?(?:\s+uong)?))?\s+([a-z][a-z0-9+._ -]{{1,80}}?){stop}",
        rf"\b(?:nhac\s+toi\s+uong|nhac\s+uong|nhac|uong)\s+([a-z][a-z0-9+._ -]{{1,80}}?){stop}",
        rf"\blich\s+(?:nhac|uong)(?:\s+thuoc)?\s+([a-z][a-z0-9+._ -]{{1,80}}?){stop}",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" ._-")
            if value and value not in {"nay", "do", "moi ngay", "hien tai"}:
                return value
    return None


def _extract_times(text: str) -> list[datetime_time]:
    normalized = normalize_search_text(text)
    raw = re.findall(
        r"(?<!\d)([01]?\d|2[0-3])(?:h(?:(\d{2}))?|:(\d{2}))(?!\d)",
        normalized,
    )
    values: list[datetime_time] = []
    for hour, h_minutes, colon_minutes in raw:
        minute = int(h_minutes or colon_minutes or 0)
        if minute > 59:
            continue
        value = datetime_time(hour=int(hour), minute=minute)
        if value not in values:
            values.append(value)
    return values


def _target_datetimes(text: str, *, recurrence: str) -> list[datetime]:
    normalized = normalize_search_text(text)
    zone = ZoneInfo("Asia/Ho_Chi_Minh")
    now = datetime.now(zone)
    target_date = now.date()
    if "ngay mai" in normalized:
        target_date += timedelta(days=1)
    else:
        iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", normalized)
        local = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(20\d{2}))?\b", normalized)
        try:
            if iso:
                target_date = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
            elif local:
                target_date = date(
                    int(local.group(3) or now.year),
                    int(local.group(2)),
                    int(local.group(1)),
                )
        except ValueError:
            return []
    values: list[datetime] = []
    for clock in _extract_times(text):
        candidate = datetime.combine(target_date, clock, tzinfo=zone)
        if recurrence == "daily" and candidate <= now:
            candidate += timedelta(days=1)
        values.append(candidate)
    return values


def _norm_medication(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_search_text(value)).strip()


def _matching_active(
    store: MedicationScheduleStore,
    tenant_id: str,
    patient_ref: str,
    medication: str,
):
    target = _norm_medication(medication)
    return [
        item
        for item in store.list(tenant_id, patient_ref=patient_ref)
        if item.status == "active" and _norm_medication(item.medication_name) == target
    ]


def execute_schedule_chat_command(
    *,
    text: str,
    tenant_id: str,
    patient_ref: str | None,
    store: MedicationScheduleStore = medication_schedule_store,
) -> ScheduleCommandResult:
    """Execute one explicit schedule command against the tenant-scoped store."""
    action = _action(text)
    medication = _extract_medication(text)
    normalized = normalize_search_text(text)
    recurrence = (
        "daily"
        if any(marker in normalized for marker in ("moi ngay", "hang ngay"))
        else "once"
    )

    required: list[str] = []
    if not patient_ref:
        required.append("patient_ref")
    if not medication:
        required.append("medication_name")

    if action == "create":
        targets = _target_datetimes(text, recurrence=recurrence)
        if not targets:
            required.append("scheduled_at")
        if required:
            return ScheduleCommandResult(
                status="needs_information",
                reply="Hãy cho biết hồ sơ, tên thuốc và giờ uống để tạo card lịch thuốc.",
                required_fields=required,
                extracted={
                    "patient_ref": patient_ref,
                    "medication_name": medication,
                    "action": action,
                },
            )
        existing = _matching_active(
            store, tenant_id, patient_ref or "", medication or ""
        )
        existing_slots = {
            (item.scheduled_at.hour, item.scheduled_at.minute, item.recurrence)
            for item in existing
        }
        created = []
        for scheduled_at in targets:
            slot = (scheduled_at.hour, scheduled_at.minute, recurrence)
            if slot in existing_slots:
                continue
            created.append(
                store.create(
                    tenant_id,
                    MedicationScheduleCreate(
                        patient_ref=patient_ref or "",
                        medication_name=medication or "",
                        scheduled_at=scheduled_at,
                        recurrence=recurrence,
                        source="chat",
                    ),
                )
            )
            existing_slots.add(slot)
        schedules = [*existing, *created]
        return ScheduleCommandResult(
            status="answered",
            reply=(
                f"Đã thêm {len(created)} mốc uống {medication} vào card lịch thuốc; "
                f"hiện có {len(schedules)} mốc đang hoạt động. "
                "Bạn có thể kiểm tra lại card để xác nhận giờ uống và theo dõi lịch hằng ngày."
            ),
            extracted={
                "patient_ref": patient_ref,
                "medication_name": medication,
                "recurrence": recurrence,
                "action": action,
            },
            result={
                "action": action,
                "schedules": [item.model_dump(mode="json") for item in schedules],
            },
        )

    if required:
        return ScheduleCommandResult(
            status="needs_information",
            reply="Mình cần hồ sơ và tên thuốc để thao tác đúng card lịch uống thuốc.",
            required_fields=required,
            extracted={
                "patient_ref": patient_ref,
                "medication_name": medication,
                "action": action,
            },
        )

    matches = _matching_active(
        store, tenant_id, patient_ref or "", medication or ""
    )
    if action == "view":
        return ScheduleCommandResult(
            status="answered",
            reply=(
                f"Đây là {len(matches)} card lịch uống {medication} đang hoạt động; "
                "mình không tạo thêm card mới. Bạn có thể kiểm tra các mốc giờ bên dưới "
                "và theo dõi lịch đang hoạt động."
            ),
            extracted={
                "patient_ref": patient_ref,
                "medication_name": medication,
                "action": action,
            },
            result={
                "action": action,
                "schedules": [item.model_dump(mode="json") for item in matches],
            },
        )

    if not matches:
        return ScheduleCommandResult(
            status="needs_information",
            reply=(
                f"Không tìm thấy card lịch uống {medication} đang hoạt động cho hồ sơ này. "
                "Bạn có thể kiểm tra lại tên thuốc hoặc cho biết card muốn thao tác."
            ),
            required_fields=["existing_schedule"],
            extracted={
                "patient_ref": patient_ref,
                "medication_name": medication,
                "action": action,
            },
            result={"action": action, "schedules": []},
        )

    if action == "update":
        targets = _target_datetimes(text, recurrence=matches[0].recurrence)
        if not targets:
            return ScheduleCommandResult(
                status="needs_information",
                reply="Bạn muốn đổi card lịch uống thuốc sang giờ nào?",
                required_fields=["scheduled_at"],
                extracted={
                    "patient_ref": patient_ref,
                    "medication_name": medication,
                    "action": action,
                },
            )
        requested = targets[-1]
        current = matches[0]
        updated_at = current.scheduled_at.replace(
            hour=requested.hour,
            minute=requested.minute,
            second=0,
            microsecond=0,
        )
        zone = current.scheduled_at.tzinfo or ZoneInfo("Asia/Ho_Chi_Minh")
        now = datetime.now(zone)
        if current.recurrence == "daily" and updated_at <= now:
            updated_at += timedelta(days=1)
        updated = store.update(
            tenant_id,
            current.schedule_id,
            MedicationScheduleUpdate(scheduled_at=updated_at),
        )
        for duplicate in matches[1:]:
            store.update(
                tenant_id,
                duplicate.schedule_id,
                MedicationScheduleUpdate(status="cancelled"),
            )
        schedules = [updated] if updated is not None else []
        return ScheduleCommandResult(
            status="answered",
            reply=(
                f"Đã đổi giờ uống {medication} sang "
                f"{requested.hour:02d}:{requested.minute:02d} và giữ đúng một card hoạt động. "
                "Bạn có thể kiểm tra lại card để xác nhận giờ mới và theo dõi lịch từ lần uống tiếp theo."
            ),
            extracted={
                "patient_ref": patient_ref,
                "medication_name": medication,
                "action": action,
            },
            result={
                "action": action,
                "schedules": [item.model_dump(mode="json") for item in schedules],
            },
        )

    if action == "delete":
        for item in matches:
            store.delete(tenant_id, item.schedule_id)
        verb = "xóa"
    else:
        for item in matches:
            store.update(
                tenant_id,
                item.schedule_id,
                MedicationScheduleUpdate(status="cancelled"),
            )
        verb = "tạm dừng"
    return ScheduleCommandResult(
        status="answered",
        reply=(
            f"Đã {verb} card lịch uống {medication}; card này không còn hoạt động. "
            "Bạn có thể kiểm tra danh sách lịch và theo dõi các card còn đang hoạt động."
        ),
        extracted={
            "patient_ref": patient_ref,
            "medication_name": medication,
            "action": action,
        },
        result={"action": action, "schedules": []},
    )
