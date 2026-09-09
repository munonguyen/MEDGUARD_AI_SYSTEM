"""Tenant-scoped medication reminder schedule repository."""

from __future__ import annotations

from datetime import datetime, time as datetime_time, timedelta, timezone
import re
from threading import RLock
import unicodedata
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.core.database import DatabaseManager, db_manager
from app.models.schedule import MedicationSchedule, MedicationScheduleCreate


class MedicationScheduleStore:
    def __init__(self, database: DatabaseManager = db_manager) -> None:
        self.database = database
        self._lock = RLock()

    def create(self, tenant_id: str, payload: MedicationScheduleCreate) -> MedicationSchedule:
        schedule = MedicationSchedule(
            schedule_id=str(uuid4()),
            tenant_id=tenant_id,
            patient_ref=payload.patient_ref,
            medication_name=payload.medication_name,
            dosage_text=payload.dosage_text,
            scheduled_at=payload.scheduled_at,
            recurrence=payload.recurrence,
            source=payload.source,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock, self.database.tenant_context(tenant_id) as session:
            session.execute(
                """
                INSERT INTO medication_schedules (
                    schedule_id, tenant_id, patient_ref, medication_name, dosage_text,
                    scheduled_at, recurrence, source, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule.schedule_id,
                    schedule.tenant_id,
                    schedule.patient_ref,
                    schedule.medication_name,
                    schedule.dosage_text,
                    schedule.scheduled_at.isoformat(),
                    schedule.recurrence,
                    schedule.source,
                    schedule.status,
                    schedule.created_at.isoformat(),
                ),
            )
        return schedule

    def list(self, tenant_id: str, patient_ref: str | None = None) -> list[MedicationSchedule]:
        query = "SELECT * FROM medication_schedules WHERE tenant_id = ?"
        params: tuple[str, ...] = (tenant_id,)
        if patient_ref:
            query += " AND patient_ref = ?"
            params += (patient_ref,)
        query += " ORDER BY scheduled_at ASC"
        with self._lock, self.database.tenant_context(tenant_id) as session:
            rows = session.execute(query, params)
        return [MedicationSchedule.model_validate(row) for row in rows]


medication_schedule_store = MedicationScheduleStore()


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn").replace("đ", "d")


def _prescription_times(entity: dict) -> list[datetime_time]:
    instructions = _normalize(str(entity.get("instructions") or ""))
    explicit = re.findall(
        r"(?<!\d)([01]?\d|2[0-3])(?:h(?:(\d{2}))?|:(\d{2}))(?!\d)",
        instructions,
    )
    values = [
        datetime_time(hour=int(hour), minute=int(h_minutes or colon_minutes or 0))
        for hour, h_minutes, colon_minutes in explicit
        if int(h_minutes or colon_minutes or 0) <= 59
    ]
    if not values:
        period_defaults = (("sang", 8), ("trua", 12), ("chieu", 17), ("toi", 20))
        values = [datetime_time(hour=hour) for marker, hour in period_defaults if marker in instructions]
    if not values:
        frequency = _normalize(str(entity.get("frequency") or ""))
        frequency_match = re.search(r"([1-4])\s*lan", frequency)
        defaults = {
            1: (8,),
            2: (8, 20),
            3: (8, 14, 20),
            4: (8, 12, 17, 21),
        }
        values = [datetime_time(hour=hour) for hour in defaults.get(int(frequency_match.group(1)), ())] if frequency_match else []
    return list(dict.fromkeys(values))


def create_from_confirmed_prescription(
    tenant_id: str,
    patient_ref: str,
    result: dict,
) -> list[MedicationSchedule]:
    """Create reminders only after the caller has completed human review."""
    local_zone = ZoneInfo("Asia/Ho_Chi_Minh")
    now = datetime.now(local_zone)
    schedules: list[MedicationSchedule] = []
    for medication in result.get("extracted_medications", []):
        entity = medication.get("extracted_entity") or {}
        name = str(entity.get("medicine_name") or "").strip()
        if not name:
            continue
        for reminder_time in _prescription_times(entity):
            scheduled_at = datetime.combine(now.date(), reminder_time, tzinfo=local_zone)
            if scheduled_at <= now:
                scheduled_at += timedelta(days=1)
            schedules.append(
                medication_schedule_store.create(
                    tenant_id,
                    MedicationScheduleCreate(
                        patient_ref=patient_ref,
                        medication_name=name,
                        dosage_text=entity.get("instructions") or entity.get("strength"),
                        scheduled_at=scheduled_at,
                        recurrence="daily",
                        source="prescription_review",
                    ),
                )
            )
    return schedules
