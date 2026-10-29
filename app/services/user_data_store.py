"""Tenant and User-scoped durable data store on TiDB Cloud / SQLite."""

from __future__ import annotations

import datetime
import json
import time
from typing import Any
from uuid import uuid4

from app.core.database import DatabaseManager, db_manager
from app.core.repository import UserSpendingRepository, HealthTwinRepository, spending_repository, health_twin_repository


class UserDataStore:
    def __init__(
        self,
        database: DatabaseManager = db_manager,
        spending_repo: UserSpendingRepository | None = None,
        twin_repo: HealthTwinRepository | None = None,
    ) -> None:
        self.database = database
        self.spending_repo = spending_repo or UserSpendingRepository(database)
        self.twin_repo = twin_repo or HealthTwinRepository(database)

    # -------------------------------------------------------------
    # User Spending Transactions
    # -------------------------------------------------------------
    def get_spending(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        return self.spending_repo.get_user_transactions(tenant_id, user_id)

    def add_spending(
        self,
        tenant_id: str,
        user_id: str,
        title: str,
        amount_vnd: int,
        category: str = "medication",
        provider: str = "",
        doctor: str = "",
        bhyt_covered_vnd: int = 0,
        is_gpp: bool = True,
        raw_date: str = "",
    ) -> dict[str, Any]:
        return self.spending_repo.add_transaction(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            amount_vnd=int(amount_vnd),
            category=category,
            provider=provider,
            doctor=doctor,
            bhyt_covered_vnd=int(bhyt_covered_vnd),
            is_gpp=is_gpp,
            raw_date=raw_date,
        )

    def delete_spending(self, tenant_id: str, user_id: str, tx_id: str) -> bool:
        with self.database.tenant_context(tenant_id) as session:
            session.execute(
                "DELETE FROM user_spending WHERE user_id = ? AND id = ?",
                (user_id, tx_id),
            )
            return True

    def clear_spending(self, tenant_id: str, user_id: str) -> bool:
        with self.database.tenant_context(tenant_id) as session:
            session.execute("DELETE FROM user_spending WHERE user_id = ?", (user_id,))
        return True

    def seed_sample_spending(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        self.clear_spending(tenant_id, user_id)
        samples = [
            {
                "title": "Thuốc Nexium 40mg & Phosphalugel Gel",
                "amount_vnd": 480000,
                "category": "medication",
                "provider": "Nhà thuốc Long Châu - Chuẩn GPP",
                "doctor": "BS. CKI Trần Minh Đức",
                "bhyt_covered_vnd": 384000,
                "is_gpp": True,
                "raw_date": "2026-10-24",
            },
            {
                "title": "Công khám Chuyên khoa Tiêu Hóa & Nội soi",
                "amount_vnd": 650000,
                "category": "clinic",
                "provider": "Bệnh viện Đa khoa Quốc tế",
                "doctor": "BS. CKI Trần Minh Đức",
                "bhyt_covered_vnd": 520000,
                "is_gpp": True,
                "raw_date": "2026-10-24",
            },
            {
                "title": "Xét nghiệm Sinh Hóa Máu (Ure, Creatinin, GOT, GPT)",
                "amount_vnd": 320000,
                "category": "diagnostics",
                "provider": "Trung tâm Xét nghiệm Diag",
                "doctor": "BS. Nguyễn Thị Thu Hà",
                "bhyt_covered_vnd": 160000,
                "is_gpp": True,
                "raw_date": "2026-10-20",
            },
        ]
        res = []
        for s in samples:
            res.append(
                self.add_spending(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    title=s["title"],
                    amount_vnd=s["amount_vnd"],
                    category=s["category"],
                    provider=s["provider"],
                    doctor=s["doctor"],
                    bhyt_covered_vnd=s["bhyt_covered_vnd"],
                    is_gpp=s["is_gpp"],
                    raw_date=s["raw_date"],
                )
            )
        return res

    # -------------------------------------------------------------
    # User Monthly Budgets
    # -------------------------------------------------------------
    def get_budget(self, tenant_id: str, user_id: str, month_key: str = "2026-10") -> int | None:
        with self.database.tenant_context(tenant_id) as session:
            rows = session.execute(
                "SELECT budget_target_vnd FROM user_budgets WHERE user_id = ? AND month_key = ?",
                (user_id, month_key),
            )
            if rows and len(rows) > 0:
                return int(rows[0]["budget_target_vnd"])
            return None

    def set_budget(
        self, tenant_id: str, user_id: str, budget_target_vnd: int, month_key: str = "2026-10"
    ) -> int:
        now = time.time()
        with self.database.tenant_context(tenant_id) as session:
            if session.dialect in ("mysql", "tidb"):
                session.execute(
                    """
                    INSERT INTO user_budgets (user_id, month_key, budget_target_vnd, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON DUPLICATE KEY UPDATE
                        budget_target_vnd = VALUES(budget_target_vnd),
                        updated_at = VALUES(updated_at)
                    """,
                    (user_id, month_key, int(budget_target_vnd), now),
                )
            else:
                session.execute(
                    """
                    INSERT INTO user_budgets (user_id, month_key, budget_target_vnd, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (user_id, month_key) DO UPDATE SET
                        budget_target_vnd = excluded.budget_target_vnd,
                        updated_at = excluded.updated_at
                    """,
                    (user_id, month_key, int(budget_target_vnd), now),
                )
        return int(budget_target_vnd)

    # -------------------------------------------------------------
    # User Medications
    # -------------------------------------------------------------
    def get_medications(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        with self.database.tenant_context(tenant_id) as session:
            rows = session.execute(
                """
                SELECT id, user_id, name, dosage, frequency, timing, instructions, created_at
                FROM user_medications
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            return rows or []

    def add_medication(
        self,
        tenant_id: str,
        user_id: str,
        name: str,
        dosage: str = "",
        frequency: str = "Hàng ngày",
        timing: str = "Sau ăn sáng",
        instructions: str = "",
    ) -> dict[str, Any]:
        med_id = f"med_{uuid4().hex[:12]}"
        now = time.time()
        with self.database.tenant_context(tenant_id) as session:
            session.execute(
                """
                INSERT INTO user_medications (
                    id, user_id, name, dosage, frequency, timing, instructions, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (med_id, user_id, name, dosage, frequency, timing, instructions, now),
            )
        return {
            "id": med_id,
            "user_id": user_id,
            "name": name,
            "dosage": dosage,
            "frequency": frequency,
            "timing": timing,
            "instructions": instructions,
            "created_at": now,
        }

    def delete_medication(self, tenant_id: str, user_id: str, med_id: str) -> bool:
        with self.database.tenant_context(tenant_id) as session:
            session.execute(
                "DELETE FROM user_medications WHERE user_id = ? AND id = ?",
                (user_id, med_id),
            )
            return True

    # -------------------------------------------------------------
    # User Appointments
    # -------------------------------------------------------------
    def get_appointments(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        with self.database.tenant_context(tenant_id) as session:
            rows = session.execute(
                """
                SELECT id, user_id, doctor, specialty, hospital, date, time, status, created_at
                FROM user_appointments
                WHERE user_id = ?
                ORDER BY date ASC, time ASC
                """,
                (user_id,),
            )
            return rows or []

    def add_appointment(
        self,
        tenant_id: str,
        user_id: str,
        doctor: str,
        specialty: str = "Đa khoa",
        hospital: str = "Bệnh viện BookingCare",
        date: str = "",
        time_slot: str = "08:30",
        status: str = "confirmed",
    ) -> dict[str, Any]:
        appt_id = f"apt_{uuid4().hex[:12]}"
        now = time.time()
        date = date or time.strftime("%Y-%m-%d")
        with self.database.tenant_context(tenant_id) as session:
            session.execute(
                """
                INSERT INTO user_appointments (
                    id, user_id, doctor, specialty, hospital, date, time, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (appt_id, user_id, doctor, specialty, hospital, date, time_slot, status, now),
            )
        return {
            "id": appt_id,
            "user_id": user_id,
            "doctor": doctor,
            "specialty": specialty,
            "hospital": hospital,
            "date": date,
            "time": time_slot,
            "status": status,
            "created_at": now,
        }

    def delete_appointment(self, tenant_id: str, user_id: str, appt_id: str) -> bool:
        with self.database.tenant_context(tenant_id) as session:
            session.execute(
                "DELETE FROM user_appointments WHERE user_id = ? AND id = ?",
                (user_id, appt_id),
            )
            return True

    # -------------------------------------------------------------
    # Clinical Shifts & Examination Schedules (Lịch khám từ Database)
    # -------------------------------------------------------------
    def _default_seed_shifts(self, user_id: str) -> list[dict[str, Any]]:
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        week_days = [(monday + datetime.timedelta(days=i)).isoformat() for i in range(7)]
        today_str = today.isoformat()

        return [
            {
                "id": "SHIFT-001",
                "shift_type": "morning",
                "shift_name": "Ca Sáng (07:30 - 11:30)",
                "time_slot": "08:00 - 08:30",
                "date": today_str,
                "patient_ref": "BN-1082",
                "patient_name": "Nguyễn Văn An",
                "age": 58,
                "sex": "Nam",
                "phone": "0912 345 678",
                "doctor": "BS. CKII Trần Quốc Huy",
                "department": "Nội Tim mạch",
                "room": "Phòng 204 - Tầng 2",
                "purpose": "Tái khám tăng huyết áp & đau thắt ngực gắng sức, theo dõi sau can thiệp stent mạch vành 3 tháng.",
                "vitals_json": json.dumps({"bp": "135/85 mmHg", "hr": "76 bpm", "spo2": "98%", "temp": "36.8°C"}),
                "prep_notes": "Yêu cầu nhịn ăn sáng từ 22h tối hôm trước để lấy máu xét nghiệm sinh hóa lúc 07:45. Mang theo sổ đo huyết áp tại nhà.",
                "status": "in_progress",
                "priority": "high",
                "current_meds_json": json.dumps(["Amlodipine 5mg", "Aspirin 81mg", "Atorvastatin 20mg"]),
            },
            {
                "id": "SHIFT-002",
                "shift_type": "morning",
                "shift_name": "Ca Sáng (07:30 - 11:30)",
                "time_slot": "08:45 - 09:15",
                "date": week_days[1],
                "patient_ref": "BN-2041",
                "patient_name": "Trần Thị Mai",
                "age": 46,
                "sex": "Nữ",
                "phone": "0988 765 432",
                "doctor": "ThS. BS Lê Hoàng Mai",
                "department": "Nội tiết - Đái tháo đường",
                "room": "Phòng 108 - Tầng 1",
                "purpose": "Kiểm tra đường huyết định kỳ HbA1c, điều chỉnh liều insulin và metformin, khám biến chứng bàn chân.",
                "vitals_json": json.dumps({"bp": "125/80 mmHg", "hr": "82 bpm", "spo2": "99%", "temp": "36.6°C"}),
                "prep_notes": "Không uống thuốc hạ đường huyết vào buổi sáng trước khi lấy máu làm nghiệm pháp. Mang phiếu theo dõi đường huyết 14 ngày.",
                "status": "confirmed",
                "priority": "normal",
                "current_meds_json": json.dumps(["Metformin 500mg", "Gliclazide 30mg"]),
            },
            {
                "id": "SHIFT-003",
                "shift_type": "morning",
                "shift_name": "Ca Sáng (07:30 - 11:30)",
                "time_slot": "09:30 - 10:00",
                "date": week_days[2],
                "patient_ref": "BN-3095",
                "patient_name": "Vũ Minh Tuấn",
                "age": 32,
                "sex": "Nam",
                "phone": "0903 112 233",
                "doctor": "BS. CKI Phạm Thanh Tùng",
                "department": "Hô hấp & Dị ứng",
                "room": "Phòng 302 - Tầng 3",
                "purpose": "Cơn hen phế quản tái phát về đêm, ho có đờm trắng dính, đánh giá chức năng thông khí phổi (Hô hấp ký).",
                "vitals_json": json.dumps({"bp": "118/75 mmHg", "hr": "94 bpm", "spo2": "94%", "temp": "37.1°C"}),
                "prep_notes": "Ngưng xịt thuốc giãn phế quản tác dụng ngắn trước khi đo hô hấp ký tối thiểu 6 giờ (trừ khi khó thở cấp).",
                "status": "priority",
                "priority": "urgent",
                "current_meds_json": json.dumps(["Salbutamol xịt", "Seretide 25/125"]),
            },
            {
                "id": "SHIFT-004",
                "shift_type": "morning",
                "shift_name": "Ca Sáng (07:30 - 11:30)",
                "time_slot": "10:15 - 10:45",
                "date": week_days[3],
                "patient_ref": "BN-4112",
                "patient_name": "Đặng Ngọc Lan",
                "age": 64,
                "sex": "Nữ",
                "phone": "0934 556 778",
                "doctor": "BS. CKII Trần Quốc Huy",
                "department": "Nội Tim mạch",
                "room": "Phòng 204 - Tầng 2",
                "purpose": "Theo dõi rung nhĩ kịch phát và dùng thuốc chống đông kháng vitamin K (Warfarin), kiểm tra chỉ số INR.",
                "vitals_json": json.dumps({"bp": "130/82 mmHg", "hr": "88 bpm (loạn nhịp)", "spo2": "97%", "temp": "36.7°C"}),
                "prep_notes": "Mang theo kết quả xét nghiệm INR gần nhất và danh sách thực phẩm, thảo dược đã dùng trong tuần.",
                "status": "waiting",
                "priority": "high",
                "current_meds_json": json.dumps(["Warfarin 2mg", "Bisoprolol 2.5mg"]),
            },
            {
                "id": "SHIFT-005",
                "shift_type": "afternoon",
                "shift_name": "Ca Chiều (13:00 - 17:00)",
                "time_slot": "13:30 - 14:00",
                "date": today_str,
                "patient_ref": "BN-5231",
                "patient_name": "Hoàng Quốc Bảo",
                "age": 51,
                "sex": "Nam",
                "phone": "0918 889 900",
                "doctor": "ThS. BS Đỗ Thu Hằng",
                "department": "Tiêu hóa - Gan mật",
                "room": "Phòng 215 - Tầng 2",
                "purpose": "Tái khám viêm loét dạ dày tá tràng Hp (+), theo dõi sau phác đồ điều trị 14 ngày, nội soi kiểm tra.",
                "vitals_json": json.dumps({"bp": "122/78 mmHg", "hr": "74 bpm", "spo2": "99%", "temp": "36.5°C"}),
                "prep_notes": "Nhịn ăn uống hoàn toàn từ 07h00 sáng để thực hiện nội soi gây mê đường tiêu hóa lúc 13h45.",
                "status": "confirmed",
                "priority": "normal",
                "current_meds_json": json.dumps(["Esomeprazole 40mg", "Amoxicillin 1g", "Clarithromycin 500mg"]),
            },
            {
                "id": "SHIFT-006",
                "shift_type": "afternoon",
                "shift_name": "Ca Chiều (13:00 - 17:00)",
                "time_slot": "14:30 - 15:00",
                "date": week_days[4],
                "patient_ref": "BN-6120",
                "patient_name": "Lê Thùy Dương",
                "age": 29,
                "sex": "Nữ",
                "phone": "0977 445 566",
                "doctor": "BS. CKI Phạm Thanh Tùng",
                "department": "Hô hấp & Dị ứng",
                "room": "Phòng 302 - Tầng 3",
                "purpose": "Dị ứng thức ăn nghi ngờ hải sản, phát ban mề đay diện rộng, tư vấn test lẩy da (Skin prick test).",
                "vitals_json": json.dumps({"bp": "115/70 mmHg", "hr": "80 bpm", "spo2": "99%", "temp": "36.9°C"}),
                "prep_notes": "Ngưng dùng thuốc kháng histamin (Cetirizine/Loratadine) ít nhất 5 ngày trước khi thực hiện test da.",
                "status": "waiting",
                "priority": "normal",
                "current_meds_json": json.dumps(["Fexofenadine 180mg"]),
            },
            {
                "id": "SHIFT-007",
                "shift_type": "afternoon",
                "shift_name": "Ca Chiều (13:00 - 17:00)",
                "time_slot": "15:30 - 16:00",
                "date": week_days[4],
                "patient_ref": "BN-7004",
                "patient_name": "Phạm Đức Long",
                "age": 70,
                "sex": "Nam",
                "phone": "0922 667 788",
                "doctor": "BS. CKII Trần Quốc Huy",
                "department": "Nội Tim mạch",
                "room": "Phòng 204 - Tầng 2",
                "purpose": "Suy tim mạn NYHA II, siêu âm tim Doppler màu kiểm tra phân suất tống máu EF và chức năng van tim.",
                "vitals_json": json.dumps({"bp": "110/68 mmHg", "hr": "70 bpm", "spo2": "96%", "temp": "36.6°C"}),
                "prep_notes": "Đo và ghi lại lượng nước uống cùng thể tích nước tiểu trong 24 giờ trước ngày khám.",
                "status": "confirmed",
                "priority": "high",
                "current_meds_json": json.dumps(["Furosemide 40mg", "Enalapril 5mg", "Spironolactone 25mg"]),
            },
            {
                "id": "SHIFT-008",
                "shift_type": "evening",
                "shift_name": "Ca Tối & Trực Đêm (17:30 - 21:30)",
                "time_slot": "18:00 - 18:30",
                "date": today_str,
                "patient_ref": "BN-8109",
                "patient_name": "Ngô Thanh Hằng",
                "age": 38,
                "sex": "Nữ",
                "phone": "0908 990 011",
                "doctor": "BS. Trực Cấp cứu & Nội tổng hợp",
                "department": "Khám ngoài giờ & Cấp cứu",
                "room": "Phòng Khám Đa khoa P.101",
                "purpose": "Sốt cao 39.2°C kéo dài ngày thứ 3, đau đầu dữ dội sau hốc mắt, đau nhức cơ khớp, nghi sốt xuất huyết Dengue.",
                "vitals_json": json.dumps({"bp": "105/70 mmHg", "hr": "102 bpm", "spo2": "98%", "temp": "39.2°C"}),
                "prep_notes": "Ưu tiên lấy máu test nhanh NS1 Ag Dengue và tổng phân tích tế bào máu ngoại vi khẩn cấp.",
                "status": "priority",
                "priority": "urgent",
                "current_meds_json": json.dumps(["Paracetamol 500mg (dùng hạ sốt)"]),
            },
            {
                "id": "SHIFT-009",
                "shift_type": "evening",
                "shift_name": "Ca Tối & Trực Đêm (17:30 - 21:30)",
                "time_slot": "19:15 - 19:45",
                "date": week_days[5],
                "patient_ref": "BN-9032",
                "patient_name": "Bùi Quốc Hưng",
                "age": 42,
                "sex": "Nam",
                "phone": "0938 123 789",
                "doctor": "BS. Trực Cấp cứu & Nội tổng hợp",
                "department": "Khám ngoài giờ & Cấp cứu",
                "room": "Phòng Khám Đa khoa P.101",
                "purpose": "Tư vấn phơi nhiễm nghề nghiệp, kiểm tra huyết áp đột ngột tăng 165/100 tại nơi làm việc.",
                "vitals_json": json.dumps({"bp": "165/100 mmHg", "hr": "90 bpm", "spo2": "98%", "temp": "37.0°C"}),
                "prep_notes": "Nghỉ ngơi tại chỗ 15 phút trước khi đo lại huyết áp 2 tay. Làm điện tâm đồ tại giường.",
                "status": "waiting",
                "priority": "high",
                "current_meds_json": json.dumps([]),
            },
        ]

    def _format_shift_row(self, row: dict[str, Any]) -> dict[str, Any]:
        vitals = {}
        try:
            if row.get("vitals_json"):
                vitals = json.loads(row["vitals_json"])
        except Exception:
            pass
        current_meds = []
        try:
            if row.get("current_meds_json"):
                current_meds = json.loads(row["current_meds_json"])
        except Exception:
            pass
        return {
            "id": row.get("id"),
            "shiftType": row.get("shift_type", "morning"),
            "shiftName": row.get("shift_name", "Ca Sáng"),
            "timeSlot": row.get("time_slot", "08:00 - 08:30"),
            "date": str(row.get("date", "")),
            "patientRef": row.get("patient_ref", "BN-1000"),
            "patientName": row.get("patient_name", "Bệnh nhân"),
            "age": int(row.get("age", 0) or 0),
            "sex": row.get("sex", "Nam"),
            "phone": row.get("phone", ""),
            "doctor": row.get("doctor", ""),
            "department": row.get("department", ""),
            "room": row.get("room", ""),
            "purpose": row.get("purpose", ""),
            "vitals": vitals,
            "prepNotes": row.get("prep_notes", ""),
            "status": row.get("status", "confirmed"),
            "priority": row.get("priority", "normal"),
            "currentMeds": current_meds,
        }

    def get_clinical_shifts(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        with self.database.tenant_context(tenant_id) as session:
            rows = session.execute(
                """
                SELECT id, user_id, shift_type, shift_name, time_slot, date,
                       patient_ref, patient_name, age, sex, phone, doctor, department,
                       room, purpose, vitals_json, prep_notes, status, priority,
                       current_meds_json, created_at, updated_at
                FROM medguard_clinical_shifts
                WHERE user_id = ?
                ORDER BY date ASC, time_slot ASC
                """,
                (user_id,),
            )
            return [self._format_shift_row(r) for r in (rows or [])]

    def seed_sample_shifts(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        now = time.time()
        with self.database.tenant_context(tenant_id) as session:
            session.execute("DELETE FROM medguard_clinical_shifts WHERE user_id = ?", (user_id,))
            seed_list = self._default_seed_shifts(user_id)
            for idx, s in enumerate(seed_list):
                unique_shift_id = f"SHIFT-{user_id[:6]}-{idx+1:03d}"
                session.execute(
                    """
                    INSERT INTO medguard_clinical_shifts (
                        id, user_id, shift_type, shift_name, time_slot, date,
                        patient_ref, patient_name, age, sex, phone, doctor, department,
                        room, purpose, vitals_json, prep_notes, status, priority,
                        current_meds_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        unique_shift_id,
                        user_id,
                        s["shift_type"],
                        s["shift_name"],
                        s["time_slot"],
                        s["date"],
                        s["patient_ref"],
                        s["patient_name"],
                        s["age"],
                        s["sex"],
                        s["phone"],
                        s["doctor"],
                        s["department"],
                        s["room"],
                        s["purpose"],
                        s["vitals_json"],
                        s["prep_notes"],
                        s["status"],
                        s["priority"],
                        s["current_meds_json"],
                        now,
                        now,
                    ),
                )
        return self.get_clinical_shifts(tenant_id, user_id)

    def clear_shifts(self, tenant_id: str, user_id: str) -> bool:
        with self.database.tenant_context(tenant_id) as session:
            session.execute("DELETE FROM medguard_clinical_shifts WHERE user_id = ?", (user_id,))
        return True

    def create_clinical_shift(
        self, tenant_id: str, user_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        shift_id = str(data.get("id") or f"SHIFT-{uuid4().hex[:6].upper()}")
        now = time.time()
        vitals_json = json.dumps(data.get("vitals") or {})
        current_meds_json = json.dumps(data.get("currentMeds") or [])

        with self.database.tenant_context(tenant_id) as session:
            session.execute(
                """
                INSERT INTO medguard_clinical_shifts (
                    id, user_id, shift_type, shift_name, time_slot, date,
                    patient_ref, patient_name, age, sex, phone, doctor, department,
                    room, purpose, vitals_json, prep_notes, status, priority,
                    current_meds_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    shift_id,
                    user_id,
                    str(data.get("shiftType", "morning")),
                    str(data.get("shiftName", "Ca Sáng")),
                    str(data.get("timeSlot", "08:00 - 08:30")),
                    str(data.get("date", datetime.date.today().isoformat())),
                    str(data.get("patientRef", "BN-1000")),
                    str(data.get("patientName", "Bệnh nhân")),
                    int(data.get("age", 0) or 0),
                    str(data.get("sex", "Nam")),
                    str(data.get("phone", "")),
                    str(data.get("doctor", "BS. Chuyên khoa")),
                    str(data.get("department", "Nội tổng hợp")),
                    str(data.get("room", "Phòng Khám P.102")),
                    str(data.get("purpose", "")),
                    vitals_json,
                    str(data.get("prepNotes", "")),
                    str(data.get("status", "confirmed")),
                    str(data.get("priority", "normal")),
                    current_meds_json,
                    now,
                    now,
                ),
            )

        return {
            "id": shift_id,
            "shiftType": data.get("shiftType", "morning"),
            "shiftName": data.get("shiftName", "Ca Sáng"),
            "timeSlot": data.get("timeSlot", "08:00 - 08:30"),
            "date": data.get("date", datetime.date.today().isoformat()),
            "patientRef": data.get("patientRef", "BN-1000"),
            "patientName": data.get("patientName", "Bệnh nhân"),
            "age": data.get("age", 0),
            "sex": data.get("sex", "Nam"),
            "phone": data.get("phone", ""),
            "doctor": data.get("doctor", ""),
            "department": data.get("department", ""),
            "room": data.get("room", ""),
            "purpose": data.get("purpose", ""),
            "vitals": data.get("vitals") or {},
            "prepNotes": data.get("prepNotes", ""),
            "status": data.get("status", "confirmed"),
            "priority": data.get("priority", "normal"),
            "currentMeds": data.get("currentMeds") or [],
        }

    def update_clinical_shift(
        self, tenant_id: str, user_id: str, shift_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        now = time.time()
        vitals_json = json.dumps(data.get("vitals") or {})
        current_meds_json = json.dumps(data.get("currentMeds") or [])

        with self.database.tenant_context(tenant_id) as session:
            session.execute(
                """
                UPDATE medguard_clinical_shifts SET
                    shift_type = ?, shift_name = ?, time_slot = ?, date = ?,
                    patient_ref = ?, patient_name = ?, age = ?, sex = ?, phone = ?,
                    doctor = ?, department = ?, room = ?, purpose = ?,
                    vitals_json = ?, prep_notes = ?, status = ?, priority = ?,
                    current_meds_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    str(data.get("shiftType", "morning")),
                    str(data.get("shiftName", "Ca Sáng")),
                    str(data.get("timeSlot", "08:00 - 08:30")),
                    str(data.get("date", "")),
                    str(data.get("patientRef", "BN-1000")),
                    str(data.get("patientName", "Bệnh nhân")),
                    int(data.get("age", 0) or 0),
                    str(data.get("sex", "Nam")),
                    str(data.get("phone", "")),
                    str(data.get("doctor", "")),
                    str(data.get("department", "")),
                    str(data.get("room", "")),
                    str(data.get("purpose", "")),
                    vitals_json,
                    str(data.get("prepNotes", "")),
                    str(data.get("status", "confirmed")),
                    str(data.get("priority", "normal")),
                    current_meds_json,
                    now,
                    shift_id,
                ),
            )
            rows = session.execute(
                "SELECT * FROM medguard_clinical_shifts WHERE id = ?", (shift_id,)
            )
            if rows:
                return self._format_shift_row(rows[0])
        return None

    def update_clinical_shift_status(
        self, tenant_id: str, user_id: str, shift_id: str, status: str
    ) -> bool:
        now = time.time()
        with self.database.tenant_context(tenant_id) as session:
            session.execute(
                "UPDATE medguard_clinical_shifts SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, shift_id),
            )
            return True

    def delete_clinical_shift(self, tenant_id: str, user_id: str, shift_id: str) -> bool:
        with self.database.tenant_context(tenant_id) as session:
            session.execute(
                "DELETE FROM medguard_clinical_shifts WHERE id = ?",
                (shift_id,),
            )
            return True

    # -------------------------------------------------------------
    # Medication Regimen & Intake Tracker (Lịch uống thuốc từ Database)
    # -------------------------------------------------------------
    def _default_seed_meds(self, user_id: str) -> list[dict[str, Any]]:
        return [
            {
                "id": "MED-001",
                "name": "Amlodipine",
                "active_substance": "Amlodipine besylate",
                "strength": "5mg",
                "dosage": "1 viên",
                "slot": "morning",
                "timing": "08:00",
                "instruction": "Uống sau bữa ăn sáng 30 phút, nuốt nguyên viên cùng nước lọc",
                "purpose": "Kiểm soát tăng huyết áp, bảo vệ thành mạch tim mạch",
                "warnings": "Không uống cùng nước bưởi chùm. Theo dõi nếu có phù mắt cá chân nhẹ.",
                "doctor": "BS. CKII Trần Quốc Huy (Tim mạch)",
                "color_theme": "blue",
            },
            {
                "id": "MED-002",
                "name": "Amoxicillin",
                "active_substance": "Amoxicillin trihydrate",
                "strength": "500mg",
                "dosage": "1 viên",
                "slot": "morning",
                "timing": "08:30",
                "instruction": "Uống sau ăn no, uống đủ liều đúng 7 ngày theo đơn chỉ định",
                "purpose": "Kháng sinh điều trị nhiễm khuẩn đường hô hấp trên",
                "warnings": "Tuyệt đối không tự ý ngưng thuốc khi thấy giảm triệu chứng.",
                "doctor": "BS. CKI Nguyễn Minh Tuấn (Tai Mũi Họng)",
                "color_theme": "teal",
            },
            {
                "id": "MED-003",
                "name": "Metformin",
                "active_substance": "Metformin hydrochloride",
                "strength": "500mg",
                "dosage": "1 viên",
                "slot": "noon",
                "timing": "12:30",
                "instruction": "Uống ngay trong hoặc sau bữa ăn trưa để tránh cồn cào dạ dày",
                "purpose": "Kiểm soát đường huyết, tăng nhạy cảm insulin (Đái tháo đường type 2)",
                "warnings": "Tránh uống rượu bia khi đang dùng thuốc.",
                "doctor": "ThS. BS Lê Hoàng Nam (Nội tiết)",
                "color_theme": "purple",
            },
            {
                "id": "MED-004",
                "name": "Esomeprazole",
                "active_substance": "Esomeprazole magnesium",
                "strength": "40mg",
                "dosage": "1 viên",
                "slot": "evening",
                "timing": "18:00",
                "instruction": "Uống trước bữa ăn tối 60 phút, nuốt nguyên viên không nhai nghiền",
                "purpose": "Ức chế tiết acid dạ dày, điều trị trào ngược dạ dày thực quản (GERD)",
                "warnings": "Không bẻ đôi hoặc nhai nát viên thuốc bao tan trong ruột.",
                "doctor": "BS. CKII Đặng Bích Thảo (Tiêu hóa)",
                "color_theme": "amber",
            },
            {
                "id": "MED-005",
                "name": "Atorvastatin",
                "active_substance": "Atorvastatin calcium",
                "strength": "20mg",
                "dosage": "1 viên",
                "slot": "evening",
                "timing": "20:00",
                "instruction": "Uống sau ăn tối, tốt nhất vào một giờ cố định mỗi ngày",
                "purpose": "Hạ cholesterol máu, ổn định mảng xơ vữa động mạch",
                "warnings": "Báo bác sĩ nếu có đau cơ hoặc mệt mỏi bất thường.",
                "doctor": "BS. CKII Trần Quốc Huy (Tim mạch)",
                "color_theme": "indigo",
            },
            {
                "id": "MED-006",
                "name": "Magnesium B6",
                "active_substance": "Magnesi lactat + Pyridoxin HCl",
                "strength": "470mg/5mg",
                "dosage": "1 viên",
                "slot": "night",
                "timing": "21:30",
                "instruction": "Uống trước khi đi ngủ 30 phút cùng nhiều nước",
                "purpose": "Bổ sung magie và vitamin B6, hỗ trợ giảm căng cơ, an thần nhẹ",
                "warnings": "Không uống cùng thời điểm với thuốc bổ sung canxi hoặc sắt.",
                "doctor": "BS. Đơn thuốc bổ trợ",
                "color_theme": "emerald",
            },
        ]

    def _format_med_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "name": row.get("name", ""),
            "activeSubstance": row.get("active_substance", ""),
            "strength": row.get("strength", ""),
            "dosage": row.get("dosage", "1 viên"),
            "slot": row.get("slot", "morning"),
            "timing": row.get("timing", "08:00"),
            "instruction": row.get("instruction", ""),
            "purpose": row.get("purpose", ""),
            "warnings": row.get("warnings", ""),
            "doctor": row.get("doctor", ""),
            "colorTheme": row.get("color_theme", "blue"),
        }

    def get_medications_regimen(self, tenant_id: str, user_id: str) -> dict[str, Any]:
        with self.database.tenant_context(tenant_id) as session:
            rows = session.execute(
                """
                SELECT id, user_id, name, active_substance, strength, dosage, slot, timing,
                       instruction, purpose, warnings, doctor, color_theme, created_at, updated_at
                FROM medguard_medications
                WHERE user_id = ?
                ORDER BY timing ASC, name ASC
                """,
                (user_id,),
            )
            # Query medication intake logs
            log_rows = session.execute(
                """
                SELECT med_id, date_str, taken
                FROM medguard_medication_logs
                WHERE user_id = ?
                """,
                (user_id,),
            )
            taken_map = {f"{r['date_str']}_{r['med_id']}": True for r in (log_rows or []) if r.get('taken')}

            return {
                "meds": [self._format_med_row(r) for r in (rows or [])],
                "takenMap": taken_map,
            }

    def seed_sample_medications(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        now = time.time()
        with self.database.tenant_context(tenant_id) as session:
            session.execute("DELETE FROM medguard_medications WHERE user_id = ?", (user_id,))
            for idx, m in enumerate(self._default_seed_meds(user_id)):
                unique_med_id = f"MED-{user_id[:6]}-{idx+1:03d}"
                session.execute(
                    """
                    INSERT INTO medguard_medications (
                        id, user_id, name, active_substance, strength, dosage, slot, timing,
                        instruction, purpose, warnings, doctor, color_theme, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        unique_med_id,
                        user_id,
                        m["name"],
                        m["active_substance"],
                        m["strength"],
                        m["dosage"],
                        m["slot"],
                        m["timing"],
                        m["instruction"],
                        m["purpose"],
                        m["warnings"],
                        m["doctor"],
                        m["color_theme"],
                        now,
                        now,
                    ),
                )
        return self.get_medications_regimen(tenant_id, user_id).get("meds", [])

    def clear_medications(self, tenant_id: str, user_id: str) -> bool:
        with self.database.tenant_context(tenant_id) as session:
            session.execute("DELETE FROM medguard_medications WHERE user_id = ?", (user_id,))
            session.execute("DELETE FROM medguard_medication_logs WHERE user_id = ?", (user_id,))
        return True


    def create_medication_regimen(
        self, tenant_id: str, user_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        med_id = str(data.get("id") or f"MED-{uuid4().hex[:6].upper()}")
        now = time.time()
        slot = str(data.get("slot", "morning"))
        color_theme = str(
            data.get("colorTheme")
            or ("blue" if slot == "morning" else "purple" if slot == "noon" else "amber" if slot == "evening" else "emerald")
        )

        with self.database.tenant_context(tenant_id) as session:
            session.execute(
                """
                INSERT INTO medguard_medications (
                    id, user_id, name, active_substance, strength, dosage, slot, timing,
                    instruction, purpose, warnings, doctor, color_theme, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    med_id,
                    user_id,
                    str(data.get("name", "")),
                    str(data.get("activeSubstance", "")),
                    str(data.get("strength", "")),
                    str(data.get("dosage", "1 viên")),
                    slot,
                    str(data.get("timing", "08:00")),
                    str(data.get("instruction", "")),
                    str(data.get("purpose", "")),
                    str(data.get("warnings", "")),
                    str(data.get("doctor", "")),
                    color_theme,
                    now,
                    now,
                ),
            )

        return {
            "id": med_id,
            "name": data.get("name", ""),
            "activeSubstance": data.get("activeSubstance", ""),
            "strength": data.get("strength", ""),
            "dosage": data.get("dosage", "1 viên"),
            "slot": slot,
            "timing": data.get("timing", "08:00"),
            "instruction": data.get("instruction", ""),
            "purpose": data.get("purpose", ""),
            "warnings": data.get("warnings", ""),
            "doctor": data.get("doctor", ""),
            "colorTheme": color_theme,
        }

    def update_medication_regimen(
        self, tenant_id: str, user_id: str, med_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        now = time.time()
        slot = str(data.get("slot", "morning"))
        color_theme = str(
            data.get("colorTheme")
            or ("blue" if slot == "morning" else "purple" if slot == "noon" else "amber" if slot == "evening" else "emerald")
        )

        with self.database.tenant_context(tenant_id) as session:
            session.execute(
                """
                UPDATE medguard_medications SET
                    name = ?, active_substance = ?, strength = ?, dosage = ?,
                    slot = ?, timing = ?, instruction = ?, purpose = ?,
                    warnings = ?, doctor = ?, color_theme = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    str(data.get("name", "")),
                    str(data.get("activeSubstance", "")),
                    str(data.get("strength", "")),
                    str(data.get("dosage", "1 viên")),
                    slot,
                    str(data.get("timing", "08:00")),
                    str(data.get("instruction", "")),
                    str(data.get("purpose", "")),
                    str(data.get("warnings", "")),
                    str(data.get("doctor", "")),
                    color_theme,
                    now,
                    med_id,
                ),
            )
            rows = session.execute(
                "SELECT * FROM medguard_medications WHERE id = ?", (med_id,)
            )
            if rows:
                return self._format_med_row(rows[0])
        return None

    def delete_medication_regimen(self, tenant_id: str, user_id: str, med_id: str) -> bool:
        with self.database.tenant_context(tenant_id) as session:
            session.execute("DELETE FROM medguard_medications WHERE id = ?", (med_id,))
            session.execute("DELETE FROM medguard_medication_logs WHERE med_id = ?", (med_id,))
            return True

    def toggle_medication_taken(
        self, tenant_id: str, user_id: str, med_id: str, date_str: str, taken: bool
    ) -> bool:
        now = time.time()
        log_id = f"log_{uuid4().hex[:12]}"
        val = 1 if taken else 0

        with self.database.tenant_context(tenant_id) as session:
            if session.dialect in ("mysql", "tidb"):
                session.execute(
                    """
                    INSERT INTO medguard_medication_logs (log_id, user_id, med_id, date_str, taken, taken_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON DUPLICATE KEY UPDATE taken = VALUES(taken), taken_at = VALUES(taken_at)
                    """,
                    (log_id, user_id, med_id, date_str, val, now),
                )
            else:
                session.execute(
                    """
                    INSERT INTO medguard_medication_logs (log_id, user_id, med_id, date_str, taken, taken_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, med_id, date_str) DO UPDATE SET
                        taken = excluded.taken,
                        taken_at = excluded.taken_at
                    """,
                    (log_id, user_id, med_id, date_str, val, now),
                )
            return True

    def reset_medication_sample(
        self, tenant_id: str, user_id: str, regimen_type: str = "cardio"
    ) -> list[dict[str, Any]]:
        now = time.time()
        with self.database.tenant_context(tenant_id) as session:
            session.execute("DELETE FROM medguard_medications WHERE user_id = ?", (user_id,))
            if regimen_type == "cardio":
                meds_to_insert = self._default_seed_meds(user_id)
            else:
                meds_to_insert = [
                    {
                        "id": f"MED-{uuid4().hex[:4].upper()}-1",
                        "name": "Amoxicillin + Clavulanic",
                        "active_substance": "Amoxicillin 875mg / Clavulanate 125mg",
                        "strength": "1000mg",
                        "dosage": "1 viên",
                        "slot": "morning",
                        "timing": "08:00",
                        "instruction": "Uống ngay đầu bữa ăn sáng để tránh kích ứng dạ dày",
                        "purpose": "Kháng sinh phổ rộng điều trị nhiễm khuẩn hô hấp",
                        "warnings": "Uống đủ 7 ngày liên tục.",
                        "doctor": "BS. Hô Hấp",
                        "color_theme": "teal",
                    },
                    {
                        "id": f"MED-{uuid4().hex[:4].upper()}-2",
                        "name": "Acetylcysteine",
                        "active_substance": "Acetylcystein 200mg",
                        "strength": "200mg",
                        "dosage": "1 gói",
                        "slot": "noon",
                        "timing": "12:30",
                        "instruction": "Hòa tan vào 100ml nước đun sôi để nguội, uống sau bữa ăn",
                        "purpose": "Long đờm, tiêu chất nhầy đường thở",
                        "warnings": "Uống nhiều nước trong ngày.",
                        "doctor": "BS. Hô Hấp",
                        "color_theme": "blue",
                    },
                    {
                        "id": f"MED-{uuid4().hex[:4].upper()}-3",
                        "name": "Fexofenadine",
                        "active_substance": "Fexofenadin hydroclorid",
                        "strength": "180mg",
                        "dosage": "1 viên",
                        "slot": "evening",
                        "timing": "19:00",
                        "instruction": "Uống cùng nước lọc, không uống cùng nước trái cây",
                        "purpose": "Kháng histamin H1 thế hệ mới, giảm hắt hơi sổ mũi dị ứng",
                        "warnings": "Thuốc không gây buồn ngủ.",
                        "doctor": "BS. Hô Hấp",
                        "color_theme": "amber",
                    },
                ]
            for m in meds_to_insert:
                session.execute(
                    """
                    INSERT INTO medguard_medications (
                        id, user_id, name, active_substance, strength, dosage, slot, timing,
                        instruction, purpose, warnings, doctor, color_theme, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        m["id"],
                        user_id,
                        m["name"],
                        m["active_substance"],
                        m["strength"],
                        m["dosage"],
                        m["slot"],
                        m["timing"],
                        m["instruction"],
                        m["purpose"],
                        m["warnings"],
                        m["doctor"],
                        m["color_theme"],
                        now,
                        now,
                    ),
                )
            rows = session.execute(
                "SELECT * FROM medguard_medications WHERE user_id = ? ORDER BY timing ASC",
                (user_id,),
            )
            return [self._format_med_row(r) for r in (rows or [])]

    # -------------------------------------------------------------
    # Aggregate Cross-Module Context for Multi-Functional Agent
    # -------------------------------------------------------------
    def get_agent_cross_module_context(self, tenant_id: str, user_id: str) -> dict[str, Any]:
        """Provides rich context for the MedGuard AI agent about the user's spending,
        budget, active medications, and upcoming doctor appointments from TiDB."""
        spending_list = self.get_spending(tenant_id, user_id)
        budget_target = self.get_budget(tenant_id, user_id) or 10_000_000
        medications = self.get_medications(tenant_id, user_id)
        appointments = self.get_appointments(tenant_id, user_id)

        total_spent = sum(int(item["amount_vnd"]) for item in spending_list)
        remaining_budget = max(0, budget_target - total_spent)

        return {
            "user_id": user_id,
            "has_records": bool(spending_list or medications or appointments),
            "spending": {
                "transaction_count": len(spending_list),
                "total_spent_vnd": total_spent,
                "monthly_budget_target_vnd": budget_target,
                "remaining_budget_vnd": remaining_budget,
                "recent_transactions": spending_list[:3],
            },
            "medications": [
                {
                    "name": m["name"],
                    "dosage": m.get("dosage", ""),
                    "timing": m.get("timing", ""),
                }
                for m in medications[:5]
            ],
            "appointments": [
                {
                    "doctor": a["doctor"],
                    "specialty": a.get("specialty", ""),
                    "date": a.get("date", ""),
                    "time": a.get("time", ""),
                }
                for a in appointments[:3]
            ],
        }


    # -------------------------------------------------------------
    # User Profile (Hồ sơ người dùng & BHYT từ TiDB)
    # -------------------------------------------------------------
    def get_user_profile(self, tenant_id: str, user_id: str) -> dict[str, Any]:
        with self.database.tenant_context(tenant_id) as session:
            rows = session.execute(
                "SELECT * FROM medguard_user_profiles WHERE user_id = ? LIMIT 1",
                (user_id,),
            )
            if rows:
                r = rows[0]
                allergies = []
                conditions = []
                emergency = {}
                try:
                    if r.get("allergies_json"):
                        allergies = json.loads(r["allergies_json"])
                except Exception:
                    pass
                try:
                    if r.get("conditions_json"):
                        conditions = json.loads(r["conditions_json"])
                except Exception:
                    pass
                try:
                    if r.get("emergency_contact_json"):
                        emergency = json.loads(r["emergency_contact_json"])
                except Exception:
                    pass
                return {
                    "user_id": r["user_id"],
                    "display_name": r.get("display_name", ""),
                    "dob": r.get("dob", ""),
                    "age": r.get("age", 0),
                    "sex": r.get("sex", ""),
                    "phone": r.get("phone", ""),
                    "email": r.get("email", ""),
                    "address": r.get("address", ""),
                    "citizen_id": r.get("citizen_id", ""),
                    "blood_type": r.get("blood_type", ""),
                    "height_cm": r.get("height_cm", 0),
                    "weight_kg": r.get("weight_kg", 0),
                    "bhyt_number": r.get("bhyt_number", ""),
                    "bhyt_hospital": r.get("bhyt_hospital", ""),
                    "bhyt_rate": r.get("bhyt_rate", 80),
                    "bhxh_number": r.get("bhxh_number", ""),
                    "vssid_status": r.get("vssid_status", "unlinked"),
                    "life_insurance_provider": r.get("life_insurance_provider", ""),
                    "life_insurance_policy_no": r.get("life_insurance_policy_no", ""),
                    "coverage_limit_vnd": r.get("coverage_limit_vnd", 0),
                    "allergies": allergies,
                    "conditions": conditions,
                    "emergency_contact": emergency,
                    "updated_at": r.get("updated_at", 0),
                }
            # Fallback query email from medguard_users
            u_rows = session.execute(
                "SELECT id, email, role FROM medguard_users WHERE id = ? LIMIT 1",
                (user_id,),
            )
            email = u_rows[0]["email"] if u_rows else ""
            default_name = email.split("@")[0] if email else "Thành viên MedGuard"
            return {
                "user_id": user_id,
                "display_name": default_name,
                "email": email,
                "dob": "",
                "age": 0,
                "sex": "",
                "phone": "",
                "address": "",
                "citizen_id": "",
                "blood_type": "",
                "height_cm": 0,
                "weight_kg": 0,
                "bhyt_number": "",
                "bhyt_hospital": "",
                "bhyt_rate": 80,
                "bhxh_number": "",
                "vssid_status": "unlinked",
                "life_insurance_provider": "",
                "life_insurance_policy_no": "",
                "coverage_limit_vnd": 0,
                "allergies": [],
                "conditions": [],
                "emergency_contact": {},
                "updated_at": time.time(),
            }

    def save_user_profile(self, tenant_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        allergies_json = json.dumps(data.get("allergies") or [])
        conditions_json = json.dumps(data.get("conditions") or [])
        emergency_json = json.dumps(data.get("emergency_contact") or {})

        with self.database.tenant_context(tenant_id) as session:
            if session.dialect in ("mysql", "tidb"):
                session.execute(
                    """
                    INSERT INTO medguard_user_profiles (
                        user_id, display_name, dob, age, sex, phone, email, address,
                        citizen_id, blood_type, height_cm, weight_kg, bhyt_number,
                        bhyt_hospital, bhyt_rate, bhxh_number, vssid_status,
                        life_insurance_provider, life_insurance_policy_no,
                        coverage_limit_vnd, allergies_json, conditions_json,
                        emergency_contact_json, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        display_name = VALUES(display_name),
                        dob = VALUES(dob),
                        age = VALUES(age),
                        sex = VALUES(sex),
                        phone = VALUES(phone),
                        email = VALUES(email),
                        address = VALUES(address),
                        citizen_id = VALUES(citizen_id),
                        blood_type = VALUES(blood_type),
                        height_cm = VALUES(height_cm),
                        weight_kg = VALUES(weight_kg),
                        bhyt_number = VALUES(bhyt_number),
                        bhyt_hospital = VALUES(bhyt_hospital),
                        bhyt_rate = VALUES(bhyt_rate),
                        bhxh_number = VALUES(bhxh_number),
                        vssid_status = VALUES(vssid_status),
                        life_insurance_provider = VALUES(life_insurance_provider),
                        life_insurance_policy_no = VALUES(life_insurance_policy_no),
                        coverage_limit_vnd = VALUES(coverage_limit_vnd),
                        allergies_json = VALUES(allergies_json),
                        conditions_json = VALUES(conditions_json),
                        emergency_contact_json = VALUES(emergency_contact_json),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        user_id,
                        str(data.get("display_name", "")),
                        str(data.get("dob", "")),
                        int(data.get("age", 0) or 0),
                        str(data.get("sex", "")),
                        str(data.get("phone", "")),
                        str(data.get("email", "")),
                        str(data.get("address", "")),
                        str(data.get("citizen_id", "")),
                        str(data.get("blood_type", "")),
                        float(data.get("height_cm", 0) or 0),
                        float(data.get("weight_kg", 0) or 0),
                        str(data.get("bhyt_number", "")),
                        str(data.get("bhyt_hospital", "")),
                        int(data.get("bhyt_rate", 80) or 80),
                        str(data.get("bhxh_number", "")),
                        str(data.get("vssid_status", "unlinked")),
                        str(data.get("life_insurance_provider", "")),
                        str(data.get("life_insurance_policy_no", "")),
                        int(data.get("coverage_limit_vnd", 0) or 0),
                        allergies_json,
                        conditions_json,
                        emergency_json,
                        now,
                    ),
                )
            else:
                session.execute(
                    """
                    INSERT INTO medguard_user_profiles (
                        user_id, display_name, dob, age, sex, phone, email, address,
                        citizen_id, blood_type, height_cm, weight_kg, bhyt_number,
                        bhyt_hospital, bhyt_rate, bhxh_number, vssid_status,
                        life_insurance_provider, life_insurance_policy_no,
                        coverage_limit_vnd, allergies_json, conditions_json,
                        emergency_contact_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (user_id) DO UPDATE SET
                        display_name = excluded.display_name,
                        dob = excluded.dob,
                        age = excluded.age,
                        sex = excluded.sex,
                        phone = excluded.phone,
                        email = excluded.email,
                        address = excluded.address,
                        citizen_id = excluded.citizen_id,
                        blood_type = excluded.blood_type,
                        height_cm = excluded.height_cm,
                        weight_kg = excluded.weight_kg,
                        bhyt_number = excluded.bhyt_number,
                        bhyt_hospital = excluded.bhyt_hospital,
                        bhyt_rate = excluded.bhyt_rate,
                        bhxh_number = excluded.bhxh_number,
                        vssid_status = excluded.vssid_status,
                        life_insurance_provider = excluded.life_insurance_provider,
                        life_insurance_policy_no = excluded.life_insurance_policy_no,
                        coverage_limit_vnd = excluded.coverage_limit_vnd,
                        allergies_json = excluded.allergies_json,
                        conditions_json = excluded.conditions_json,
                        emergency_contact_json = excluded.emergency_contact_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        user_id,
                        str(data.get("display_name", "")),
                        str(data.get("dob", "")),
                        int(data.get("age", 0) or 0),
                        str(data.get("sex", "")),
                        str(data.get("phone", "")),
                        str(data.get("email", "")),
                        str(data.get("address", "")),
                        str(data.get("citizen_id", "")),
                        str(data.get("blood_type", "")),
                        float(data.get("height_cm", 0) or 0),
                        float(data.get("weight_kg", 0) or 0),
                        str(data.get("bhyt_number", "")),
                        str(data.get("bhyt_hospital", "")),
                        int(data.get("bhyt_rate", 80) or 80),
                        str(data.get("bhxh_number", "")),
                        str(data.get("vssid_status", "unlinked")),
                        str(data.get("life_insurance_provider", "")),
                        str(data.get("life_insurance_policy_no", "")),
                        int(data.get("coverage_limit_vnd", 0) or 0),
                        allergies_json,
                        conditions_json,
                        emergency_json,
                        now,
                    ),
                )
        return self.get_user_profile(tenant_id, user_id)


user_data_store = UserDataStore()
