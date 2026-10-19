from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from app.models.health_twin import (
    OrganCoordinates,
    OrganStatus,
    PatientHealthProfile,
    RecoveryTimelinePoint,
    SafeGuardrailAlert,
    VitalSignsSummary,
)


def _get_default_organs() -> list[OrganStatus]:
    return [
        OrganStatus(
            id="head",
            name="Head & Brain",
            vietnamese_name="Đầu & Thần kinh",
            status="monitoring",
            health_score=75,
            pain_level=4,
            inflammation_level="mild",
            symptoms=["Đau đầu căng thẳng", "Nặng trán"],
            clinical_notes="Ghi nhận đau âm ỉ vùng trán và thái dương do cảm cúm đường hô hấp trên.",
            related_medications=["Paracetamol 500mg"],
            coordinates=OrganCoordinates(x=50.0, y=13.0),
        ),
        OrganStatus(
            id="ent",
            name="Ear, Nose & Throat",
            vietnamese_name="Tai Mũi Họng",
            status="inflamed",
            health_score=65,
            pain_level=3,
            inflammation_level="moderate",
            symptoms=["Sổ mũi nước trong", "Nghẹt mũi nhẹ", "Rát họng"],
            clinical_notes="Phù nề niêm mạc mũi họng do virus cảm cúm.",
            related_medications=["Xịt mũi nước muối biển", "Súc họng NaCl 0.9%"],
            coordinates=OrganCoordinates(x=50.0, y=20.0),
        ),
        OrganStatus(
            id="cardiovascular",
            name="Cardiovascular",
            vietnamese_name="Tim mạch",
            status="normal",
            health_score=95,
            pain_level=0,
            inflammation_level="none",
            symptoms=[],
            clinical_notes="Huyết áp 120/80 mmHg, nhịp tim đều 78 bpm, không đau ngực.",
            related_medications=[],
            coordinates=OrganCoordinates(x=53.5, y=30.0),
        ),
        OrganStatus(
            id="lungs",
            name="Respiratory & Lungs",
            vietnamese_name="Phổi & Hô hấp",
            status="monitoring",
            health_score=85,
            pain_level=1,
            inflammation_level="mild",
            symptoms=["Thỉnh thoảng húng hắng ho nhẹ"],
            clinical_notes="SpO2 98%, phế bào êm, không ran, đường thở dưới thông thoáng.",
            related_medications=[],
            coordinates=OrganCoordinates(x=46.0, y=32.0),
        ),
        OrganStatus(
            id="stomach",
            name="Gastrointestinal & Stomach",
            vietnamese_name="Dạ dày & Tiêu hoá",
            status="normal",
            health_score=92,
            pain_level=0,
            inflammation_level="none",
            symptoms=[],
            clinical_notes="Bụng mềm, không chướng, tiêu hóa bình thường. Cần lưu ý uống thuốc sau ăn.",
            related_medications=[],
            coordinates=OrganCoordinates(x=48.0, y=41.5),
        ),
        OrganStatus(
            id="liver",
            name="Liver & Metabolism",
            vietnamese_name="Gan & Chuyển hoá",
            status="normal",
            health_score=96,
            pain_level=0,
            inflammation_level="none",
            symptoms=[],
            clinical_notes="Chức năng chuyển hóa ổn định. Chú ý không dùng Paracetamol quá 3000mg/24h.",
            related_medications=[],
            coordinates=OrganCoordinates(x=42.0, y=44.0),
        ),
        OrganStatus(
            id="kidneys",
            name="Kidneys & Urinary",
            vietnamese_name="Thận & Tiết niệu",
            status="normal",
            health_score=98,
            pain_level=0,
            inflammation_level="none",
            symptoms=[],
            clinical_notes="Đào thải bình thường, duy trì uống đủ 2 lít nước ấm mỗi ngày.",
            related_medications=[],
            coordinates=OrganCoordinates(x=58.0, y=46.0),
        ),
        OrganStatus(
            id="spine_joints",
            name="Spine & Musculoskeletal",
            vietnamese_name="Cơ xương khớp & Cột sống",
            status="monitoring",
            health_score=80,
            pain_level=2,
            inflammation_level="mild",
            symptoms=["Hơi mỏi người do sốt"],
            clinical_notes="Mỏi cơ nhẹ toàn thân điển hình trong hội chứng cúm.",
            related_medications=[],
            coordinates=OrganCoordinates(x=50.0, y=68.0),
        ),
        OrganStatus(
            id="skin",
            name="Skin & Immune System",
            vietnamese_name="Da liễu & Hệ miễn dịch",
            status="normal",
            health_score=95,
            pain_level=0,
            inflammation_level="none",
            symptoms=[],
            clinical_notes="Da ấm, không phát ban, không nổi mề đay dị ứng thuốc.",
            related_medications=[],
            coordinates=OrganCoordinates(x=22.0, y=52.0),
        ),
    ]


class PatientHealthTwinService:
    """Manages the interactive anatomical health twin, recovery timeline,
    and clinical safety guardrails for patient episodes."""

    def __init__(self) -> None:
        self._current_profile: PatientHealthProfile = self._build_default_flu_profile()

    def get_profile(self) -> PatientHealthProfile:
        return self._current_profile

    def switch_scenario(self, scenario_id: str) -> PatientHealthProfile:
        now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
        if scenario_id == "initial_flu":
            self._current_profile = self._build_default_flu_profile()
        elif scenario_id == "recovered_headache":
            self._current_profile = self._build_recovered_profile(now_str)
        elif scenario_id == "adr_stomach_nsaid":
            self._current_profile = self._build_adr_stomach_profile(now_str)
        elif scenario_id == "severe_fever_progression":
            self._current_profile = self._build_severe_progression_profile(now_str)
        elif scenario_id == "healthy_baseline":
            self._current_profile = self._build_healthy_profile(now_str)
        return self._current_profile

    def evaluate_progress(
        self,
        message: str,
        current_medications: list[str] | None = None,
        vital_updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyzes patient's latest update, adjusts anatomical organ status,
        updates overall health score, and enforces AI safety directives."""
        norm = message.lower().strip()
        now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
        profile = self._current_profile

        # 1. Detect Improvement / Recovery
        # E.g., "hết đau đầu", "hết sổ mũi", "hết sốt", "khỏe hơn", "khỏi bệnh", "đỡ nhiều"
        recovery_patterns = [
            r"hết\s*(đau đầu|nhức đầu|sổ mũi|nghẹt mũi|sốt|rát họng|ho)",
            r"không còn\s*(sốt|đau đầu|sổ mũi|mệt)",
            r"(đỡ|khỏi|bớt)\s*(hẳn|nhiều|rồi|bệnh)",
            r"khỏe hơn\s*(nhiều|rồi)",
        ]
        is_recovery = any(re.search(pat, norm) for pat in recovery_patterns)

        # 2. Detect Deterioration / Adverse Drug Reaction (ADR)
        # E.g., "uống thuốc vào bị đau dạ dày", "đau bao tử", "cồn cào", "buồn nôn sau uống", "nổi mẩn ngứa"
        adr_stomach_patterns = [
            r"(uống thuốc|dùng thuốc|sau khi uống).*?(đau dạ dày|đau bao tử|đau bụng|cồn cào|buồn nôn|nôn|rát thượng vị)",
            r"(đau dạ dày|đau bao tử|rát thượng vị|cồn cào).*?(dữ dội|nặng hơn|sau khi uống)",
            r"(đau bụng|nôn nao|buồn nôn)\s*(nhiều|hơn|dữ)",
        ]
        is_adr_stomach = any(re.search(pat, norm) for pat in adr_stomach_patterns)

        # 3. Detect Allergic Reaction / Rash
        allergy_patterns = [
            r"(nổi mẩn|phát ban|mày đay|ngứa ngáy|sưng môi|phù mặt|khó thở dị ứng)",
        ]
        is_allergy = any(re.search(pat, norm) for pat in allergy_patterns)

        # 4. Detect Severe Disease Escalation
        escalation_patterns = [
            r"(sốt cao hơn|sốt 39|sốt 40|rét run|khó thở dữ dội|đau ngực dữ dội|co giật)",
            r"(nặng hơn|không thở được|mệt lả|li bì)",
        ]
        is_escalation = any(re.search(pat, norm) for pat in escalation_patterns)

        detected_event = "inquiry"
        ai_analysis = ""
        action_plan = ""
        must_discontinue = False
        discontinued_items: list[str] = []

        if is_adr_stomach:
            detected_event = "adverse_reaction"
            must_discontinue = True
            discontinued_items = ["Thuốc kháng viêm giảm đau (NSAID nghi ngờ)"]
            ai_analysis = (
                "AI MedGuard phát hiện dấu hiệu Phản ứng Bất lợi của Thuốc (ADR): Kích ứng và tổn thương niêm mạc "
                "dạ dày - thượng vị do dùng thuốc giảm đau/kháng viêm (NSAID). "
                "Cần ngưng ngay lập tức để ngăn ngừa nguy cơ xuất huyết tiêu hóa."
            )
            action_plan = (
                "1. HẠN CHẾ VÀ NGỪNG NGAY thuốc giảm đau NSAID đang dùng.\n"
                "2. Chuyển sang biện pháp hỗ trợ: Uống nước ấm, dùng thuốc bảo vệ niêm mạc dạ dày (antacid/PPI) nếu có chỉ định.\n"
                "3. Tuyệt đối không để bụng đói khi uống bất kỳ loại thuốc nào.\n"
                "4. Khám chuyên khoa tiêu hóa ngay nếu xuất hiện nôn mửa dữ dội hoặc đi ngoài phân đen."
            )
            # Apply changes to profile
            profile = self._apply_adr_stomach_to_profile(profile, now_str, message)

        elif is_allergy:
            detected_event = "adverse_reaction"
            must_discontinue = True
            discontinued_items = ["Toàn bộ kháng sinh / thuốc mới uống gần nhất"]
            ai_analysis = (
                "AI MedGuard phát hiện dấu hiệu dị ứng thuốc cấp: Nổi mẩn, ngứa, phát ban trên da. "
                "Nguy cơ tiến triển phản vệ nếu tiếp tục sử dụng."
            )
            action_plan = (
                "1. NGỪNG NGAY LẬP TỨC loại thuốc mới uống.\n"
                "2. Uống nhiều nước, theo dõi sát đường thở.\n"
                "3. Nếu xuất hiện sưng mắt/môi hoặc cảm giác nghẹn thở, gọi cấp cứu 115 ngay lập tức."
            )
            profile = self._apply_allergy_to_profile(profile, now_str, message)

        elif is_escalation:
            detected_event = "deterioration"
            ai_analysis = (
                "AI MedGuard phát hiện dấu hiệu bệnh tiến triển tăng nặng (sốt cao kịch phát hoặc suy giảm hô hấp). "
                "Cách chăm sóc tại nhà hiện tại không còn đủ an toàn, cần can thiệp y tế chuyên sâu."
            )
            action_plan = (
                "1. Không tiếp tục tự điều trị tại nhà với liều thông thường.\n"
                "2. Chườm ấm hạ sốt và khẩn trương di chuyển đến bệnh viện hoặc phòng khám gần nhất.\n"
                "3. Sẵn sàng gọi xe cứu thương 115 nếu có khó thở hoặc lơ mơ."
            )
            profile = self._apply_escalation_to_profile(profile, now_str, message)

        elif is_recovery:
            detected_event = "recovery"
            ai_analysis = (
                "AI MedGuard ghi nhận sự thuyên giảm triệu chứng rõ rệt: Bệnh nhân hết đau đầu, sổ mũi, "
                "thân nhiệt trở về ngưỡng an toàn. Thể trạng đang bước vào giai đoạn hồi phục tích cực."
            )
            action_plan = (
                "1. Ngừng uống thuốc hạ sốt giảm đau Paracetamol khi đã hết đau/hết sốt hoàn toàn.\n"
                "2. Duy trì xịt rửa mũi nước muối sinh lý thêm 2-3 ngày để niêm mạc phục hồi hoàn toàn.\n"
                "3. Bổ sung dinh dưỡng, uống nước hoa quả giàu vitamin C và nghỉ ngơi điều độ."
            )
            profile = self._apply_recovery_to_profile(profile, now_str, message)

        else:
            detected_event = "inquiry"
            ai_analysis = "Hệ thống ghi nhận thông tin theo dõi sức khoẻ định kỳ của bệnh nhân."
            action_plan = "Tiếp tục theo dõi các chỉ số sinh hiệu và thực hiện theo phác đồ bác sĩ đã dặn."

        self._current_profile = profile
        return {
            "status": "success",
            "detected_event": detected_event,
            "ai_analysis": ai_analysis,
            "action_plan": action_plan,
            "must_discontinue_previous": must_discontinue,
            "discontinued_items": discontinued_items,
            "profile": profile,
        }

    # Internal Profile Builders
    def _build_default_flu_profile(self) -> PatientHealthProfile:
        now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
        return PatientHealthProfile(
            patient_id="demo-patient-001",
            patient_name="Bệnh nhân MedGuard",
            age=34,
            gender="Nam",
            active_diagnosis="Hội chứng Cảm cúm & Viêm đường hô hấp trên",
            overall_health_score=74,
            health_trend="stable",
            vitals=VitalSignsSummary(
                heart_rate_bpm=82,
                blood_pressure_systolic=122,
                blood_pressure_diastolic=80,
                temperature_celsius=38.2,
                spo2_percent=98,
                overall_pain_level=4,
            ),
            organs=_get_default_organs(),
            active_medications=["Paracetamol 500mg (khi sốt >38.5°C)", "Xịt mũi nước muối biển"],
            discontinued_medications=[],
            contraindicated_regimens=[],
            clinical_directives=[
                "Uống nhiều nước ấm (2-2.5 lít/ngày)",
                "Nghỉ ngơi tại phòng thoáng khí",
                "Theo dõi nhiệt độ cơ thể mỗi 4-6 giờ",
            ],
            safe_guardrail_alert=None,
            timeline=[
                RecoveryTimelinePoint(
                    id="t1",
                    timestamp="08:30 Hôm nay",
                    phase="initial_onset",
                    title="Khởi phát triệu chứng cúm",
                    trigger_message="Tôi bị sốt 38.2 độ, đau đầu và sổ mũi, rát họng.",
                    health_score=74,
                    status_label="Thăm dò ban đầu",
                    clinical_summary="Khởi phát hội chứng cúm mùa. Đau đầu và viêm niêm mạc mũi họng rõ.",
                    ai_directive="Hướng dẫn dùng Paracetamol 500mg cách 4-6h nếu sốt, xịt mũi nước muối sinh lý.",
                    medications_adjusted=["Kê Paracetamol 500mg", "Xịt mũi nước muối"],
                )
            ],
            last_updated=now_str,
        )

    def _build_recovered_profile(self, now_str: str) -> PatientHealthProfile:
        organs = _get_default_organs()
        for organ in organs:
            if organ.id in ["head", "ent", "spine_joints"]:
                organ.status = "normal"
                organ.health_score = 96
                organ.pain_level = 0
                organ.inflammation_level = "none"
                organ.symptoms = []
                organ.clinical_notes = "Đã hết đau nhức, đường thở thông thoáng hoàn toàn."

        return PatientHealthProfile(
            patient_id="demo-patient-001",
            patient_name="Bệnh nhân MedGuard",
            age=34,
            gender="Nam",
            active_diagnosis="Hồi phục sau Cảm cúm (Đã hết triệu chứng)",
            overall_health_score=95,
            health_trend="improving",
            vitals=VitalSignsSummary(
                heart_rate_bpm=74,
                blood_pressure_systolic=118,
                blood_pressure_diastolic=78,
                temperature_celsius=36.8,
                spo2_percent=99,
                overall_pain_level=0,
            ),
            organs=organs,
            active_medications=["Nước muối sinh lý vệ sinh mũi họng"],
            discontinued_medications=["Paracetamol 500mg (Dừng do đã cắt sốt & hết đau đầu)"],
            contraindicated_regimens=[],
            clinical_directives=[
                "Dừng thuốc giảm đau hạ sốt Paracetamol",
                "Tiếp tục uống đủ nước và tăng cường dinh dưỡng hoa quả",
                "Có thể trở lại sinh hoạt và làm việc nhẹ nhàng bình thường",
            ],
            safe_guardrail_alert=None,
            timeline=[
                RecoveryTimelinePoint(
                    id="t1",
                    timestamp="08:30 Hôm qua",
                    phase="initial_onset",
                    title="Khởi phát triệu chứng cúm",
                    trigger_message="Tôi bị sốt 38.2 độ, đau đầu và sổ mũi, rát họng.",
                    health_score=74,
                    status_label="Thăm dò ban đầu",
                    clinical_summary="Hội chứng cúm mùa, đau đầu, nghẹt mũi.",
                    ai_directive="Dùng Paracetamol 500mg và nước muối sinh lý.",
                    medications_adjusted=["Kê Paracetamol 500mg"],
                ),
                RecoveryTimelinePoint(
                    id="t2",
                    timestamp="14:00 Hôm nay",
                    phase="improved_recovering",
                    title="Thuyên giảm & Hết triệu chứng",
                    trigger_message="Hôm nay tôi đã hết đau đầu và sổ mũi rồi, người thấy rất khoẻ.",
                    health_score=95,
                    status_label="Hồi phục tốt (95%)",
                    clinical_summary="Nhiệt độ 36.8°C ổn định, đau đầu biến mất, đường hô hấp thông thoáng.",
                    ai_directive="Khuyến nghị ngừng thuốc Paracetamol, duy trì giữ ấm và bổ sung vitamin C.",
                    medications_adjusted=["Dừng Paracetamol 500mg"],
                ),
            ],
            last_updated=now_str,
        )

    def _build_adr_stomach_profile(self, now_str: str) -> PatientHealthProfile:
        organs = _get_default_organs()
        for organ in organs:
            if organ.id == "stomach":
                organ.status = "adverse_reaction"
                organ.health_score = 38
                organ.pain_level = 7
                organ.inflammation_level = "severe"
                organ.symptoms = ["Đau quặn thượng vị", "Cồn cào nóng rát", "Buồn nôn sau uống thuốc"]
                organ.clinical_notes = "Kích ứng niêm mạc dạ dày cấp nghi do thuốc chống viêm giảm đau NSAID."
                organ.warning = "CẢNH BÁO TÁC DỤNG PHỤ: Nguy cơ viêm loét niêm mạc dạ dày cấp!"
                organ.is_adverse_reaction = True
                organ.contraindicated_actions = [
                    "TIẾP TỤC UỐNG THUỐC NSAID/ASPIRIN",
                    "Uống thuốc khi bụng đói",
                    "Dùng đồ cay nóng, cà phê, rượu bia",
                ]

        return PatientHealthProfile(
            patient_id="demo-patient-001",
            patient_name="Bệnh nhân MedGuard",
            age=34,
            gender="Nam",
            active_diagnosis="Tác dụng phụ dạ dày cấp do thuốc (NSAID-induced Gastritis)",
            overall_health_score=52,
            health_trend="critical_alert",
            vitals=VitalSignsSummary(
                heart_rate_bpm=92,
                blood_pressure_systolic=130,
                blood_pressure_diastolic=84,
                temperature_celsius=37.2,
                spo2_percent=98,
                overall_pain_level=7,
            ),
            organs=organs,
            active_medications=["Nước ấm", "Men vi sinh / Thuốc tráng bao tử (nếu có)"],
            discontinued_medications=["Ibuprofen / Thuốc giảm đau NSAID (NGỪNG KHẨN CẤP)"],
            contraindicated_regimens=[
                "Tiếp tục uống thuốc giảm đau NSAID",
                "Tự ý tăng liều thuốc khi đau bụng",
            ],
            clinical_directives=[
                "NGỪNG NGAY LẬP TỨC thuốc giảm đau NSAID đang dùng",
                "Không để bụng đói, uống nước ấm từng ngụm nhỏ",
                "Đến cơ sở y tế gần nhất nếu đau quặn dữ dội hoặc có nôn ra máu / đi ngoài phân đen",
            ],
            safe_guardrail_alert=SafeGuardrailAlert(
                alert_level="danger",
                title="HẠN CHẾ CÁCH CŨ: Dừng ngay thuốc giảm đau gây hại dạ dày",
                cause_identified="Bệnh nhân phát sinh đau rát thượng vị và buồn nôn dữ dội sau khi uống thuốc.",
                contraindicated_item="Thuốc chống viêm giảm đau NSAID (Ibuprofen, Aspirin, Diclofenac)",
                required_action="DỪNG NGAY LẬP TỨC cách uống thuốc cũ. Tuyệt đối không tiếp tục uống viên kế tiếp.",
                alternative_recommendation="Uống nước ấm, nằm nghỉ ngơi đầu cao, tham vấn dược sĩ dùng thuốc bảo vệ niêm mạc (Antacid). Khám tiêu hóa nếu đau kéo dài.",
                seek_emergency=False,
            ),
            timeline=[
                RecoveryTimelinePoint(
                    id="t1",
                    timestamp="08:30 Hôm qua",
                    phase="initial_onset",
                    title="Khởi phát triệu chứng cúm",
                    trigger_message="Tôi bị sốt 38.2 độ, đau đầu và sổ mũi, rát họng.",
                    health_score=74,
                    status_label="Thăm dò ban đầu",
                    clinical_summary="Bắt đầu điều trị cảm cúm.",
                    ai_directive="Kê thuốc hạ sốt giảm đau.",
                    medications_adjusted=["Bắt đầu dùng thuốc giảm đau"],
                ),
                RecoveryTimelinePoint(
                    id="t2",
                    timestamp="11:30 Hôm nay",
                    phase="adverse_event_escalation",
                    title="Phát sinh tác dụng phụ đau dạ dày cấp",
                    trigger_message="Uống thuốc vào bỗng bị đau dạ dày dữ dội, cồn cào buồn nôn rát bụng.",
                    health_score=52,
                    status_label="Cảnh báo ADR nguy cơ cao",
                    clinical_summary="Kích ứng niêm mạc dạ dày cấp do NSAID. Đau thượng vị 7/10.",
                    ai_directive="AI Guardrail: BẮT BUỘC DỪNG CÁCH CŨ. Ngừng ngay NSAID, đổi sang bảo vệ tiêu hóa.",
                    medications_adjusted=["NGỪNG KHẨN CẤP: Ibuprofen/NSAID"],
                ),
            ],
            last_updated=now_str,
        )

    def _build_severe_progression_profile(self, now_str: str) -> PatientHealthProfile:
        organs = _get_default_organs()
        for organ in organs:
            if organ.id in ["head", "lungs", "cardiovascular"]:
                organ.status = "critical"
                organ.health_score = 42
                organ.pain_level = 6
                organ.inflammation_level = "severe"
                organ.symptoms = ["Sốt cao 39.5°C rét run", "Thở gấp, đau tức ngực", "Mệt lả toàn thân"]
                organ.warning = "CẢNH BÁO BỆNH TIẾN TRIỂN NẶNG: Nguy cơ nhiễm trùng phế quản phổi!"

        return PatientHealthProfile(
            patient_id="demo-patient-001",
            patient_name="Bệnh nhân MedGuard",
            age=34,
            gender="Nam",
            active_diagnosis="Sốt cao tiến triển kịch phát - Nghi ngờ bội nhiễm đường hô hấp",
            overall_health_score=46,
            health_trend="critical_alert",
            vitals=VitalSignsSummary(
                heart_rate_bpm=110,
                blood_pressure_systolic=138,
                blood_pressure_diastolic=88,
                temperature_celsius=39.5,
                spo2_percent=94,
                overall_pain_level=6,
            ),
            organs=organs,
            active_medications=["Oresol bù nước", "Hạ sốt khẩn cấp"],
            discontinued_medications=[],
            contraindicated_regimens=["Tự ý mua kháng sinh uống tại nhà khi chưa xét nghiệm máu"],
            clinical_directives=[
                "CẦN ĐẾN CƠ SỞ Y TẾ HOẶC PHÒNG CẤP CỨU NGAY LẬP TỨC",
                "Chườm ấm vùng trán, nách, bẹn trong thời gian chờ di chuyển",
                "Uống oresol từng ngụm nhỏ bù điện giải",
            ],
            safe_guardrail_alert=SafeGuardrailAlert(
                alert_level="critical",
                title="BÁO ĐỘNG ĐỎ: Triệu chứng vượt ngưỡng an toàn điều trị tại nhà",
                cause_identified="Sốt cao 39.5°C kèm SpO2 giảm xuống 94% và thở dốc.",
                contraindicated_item="Tiếp tục nằm nhà theo dõi thông thường",
                required_action="CHUYỂN NGAY TỚI BỆNH VIỆN / TRUNG TÂM Y TẾ GẦN NHẤT",
                alternative_recommendation="Sử dụng chức năng 'Chỉ đường Real-time' trong MedGuard để đến viện nhanh nhất.",
                seek_emergency=True,
            ),
            timeline=[
                RecoveryTimelinePoint(
                    id="t1",
                    timestamp="Hôm qua",
                    phase="initial_onset",
                    title="Khởi phát cúm",
                    trigger_message="Sốt nhẹ 38.2 độ, đau đầu.",
                    health_score=74,
                    status_label="Theo dõi ban đầu",
                    clinical_summary="Điều trị cảm cúm ban đầu.",
                    ai_directive="Uống Paracetamol hạ sốt.",
                    medications_adjusted=[],
                ),
                RecoveryTimelinePoint(
                    id="t2",
                    timestamp="Hôm nay",
                    phase="adverse_event_escalation",
                    title="Tiến triển nặng - Sốt kịch phát",
                    trigger_message="Bỗng nhiên sốt cao 39.5 độ, rét run, khó thở và mệt lả.",
                    health_score=46,
                    status_label="Báo động nguy kịch",
                    clinical_summary="SpO2 tụt 94%, mạch nhanh 110 bpm, nhiệt độ 39.5°C.",
                    ai_directive="Báo động khẩn cấp: Đến ngay cơ sở y tế gần nhất, không tự điều trị tại nhà.",
                    medications_adjusted=["Ngưng phác đồ tại nhà"],
                ),
            ],
            last_updated=now_str,
        )

    def _build_healthy_profile(self, now_str: str) -> PatientHealthProfile:
        organs = _get_default_organs()
        for organ in organs:
            organ.status = "normal"
            organ.health_score = 99
            organ.pain_level = 0
            organ.inflammation_level = "none"
            organ.symptoms = []
            organ.clinical_notes = "Chức năng bình thường, chỉ số tối ưu."
            organ.warning = None
            organ.is_adverse_reaction = False
            organ.contraindicated_actions = []

        return PatientHealthProfile(
            patient_id="demo-patient-001",
            patient_name="Bệnh nhân MedGuard",
            age=34,
            gender="Nam",
            active_diagnosis="Thể trạng Khỏe mạnh - Bình thường",
            overall_health_score=98,
            health_trend="stable",
            vitals=VitalSignsSummary(
                heart_rate_bpm=72,
                blood_pressure_systolic=118,
                blood_pressure_diastolic=78,
                temperature_celsius=36.7,
                spo2_percent=99,
                overall_pain_level=0,
            ),
            organs=organs,
            active_medications=[],
            discontinued_medications=[],
            contraindicated_regimens=[],
            clinical_directives=[
                "Duy trì chế độ ăn giàu dinh dưỡng và tập thể dục 30 phút/ngày",
                "Uống đủ 2 lít nước mỗi ngày",
                "Ngủ đủ 7-8 tiếng",
            ],
            safe_guardrail_alert=None,
            timeline=[
                RecoveryTimelinePoint(
                    id="t1",
                    timestamp="Hiện tại",
                    phase="fully_resolved",
                    title="Trạng thái hoàn hảo",
                    trigger_message="Kiểm tra tổng quan sức khoẻ.",
                    health_score=98,
                    status_label="Hoàn toàn bình thường",
                    clinical_summary="Tất cả các cơ quan hoạt động tối ưu, không có bệnh lý hoạt động.",
                    ai_directive="Duy trì lối sống lành mạnh.",
                    medications_adjusted=[],
                )
            ],
            last_updated=now_str,
        )

    # Dynamic Helpers for message evaluation
    def _apply_adr_stomach_to_profile(self, current: PatientHealthProfile, now_str: str, message: str) -> PatientHealthProfile:
        p = current.model_copy(deep=True)
        p.active_diagnosis = "Kích ứng dạ dày cấp nghi do thuốc (ADR)"
        p.overall_health_score = max(35, p.overall_health_score - 25)
        p.health_trend = "critical_alert"
        p.vitals.overall_pain_level = 7
        p.vitals.heart_rate_bpm = 90

        for organ in p.organs:
            if organ.id == "stomach":
                organ.status = "adverse_reaction"
                organ.health_score = 35
                organ.pain_level = 7
                organ.inflammation_level = "severe"
                organ.symptoms = ["Đau rát cồn cào thượng vị", "Buồn nôn sau uống thuốc"]
                organ.warning = "CẢNH BÁO TÁC DỤNG PHỤ CẤP: Dừng ngay loại thuốc nghi ngờ gây hại dạ dày!"
                organ.is_adverse_reaction = True
                organ.contraindicated_actions = ["Tiếp tục uống thuốc cũ", "Uống thuốc khi đói"]

        discontinued = "Thuốc giảm đau NSAID / Kháng sinh nghi ngờ"
        if discontinued not in p.discontinued_medications:
            p.discontinued_medications.append(discontinued)

        p.safe_guardrail_alert = SafeGuardrailAlert(
            alert_level="danger",
            title="AI BẢO VỆ: Hạn chế và Dừng ngay loại thuốc đang gây hại dạ dày",
            cause_identified="Bệnh nhân ghi nhận cơn đau quặn thượng vị sau khi uống thuốc.",
            contraindicated_item="Thuốc giảm đau kháng viêm NSAID đang sử dụng",
            required_action="DỪNG NGAY CÁCH CŨ. Không uống thêm liều tiếp theo.",
            alternative_recommendation="Uống nước ấm, dùng thuốc bảo vệ niêm mạc dạ dày (Antacid). Khám tiêu hóa nếu đau tăng dần.",
            seek_emergency=False,
        )

        p.clinical_directives = [
            "NGỪNG NGAY thuốc nghi ngờ gây kích ứng dạ dày",
            "Uống nhiều nước ấm, nghỉ ngơi tại chỗ",
            "Đến viện nếu đau quặn dữ dội hoặc nôn mửa",
        ]

        p.timeline.append(
            RecoveryTimelinePoint(
                id=f"t{len(p.timeline)+1}",
                timestamp=now_str,
                phase="adverse_event_escalation",
                title="Cảnh báo phản ứng phụ đường tiêu hóa",
                trigger_message=message,
                health_score=p.overall_health_score,
                status_label="Nguy cơ ADR - Dừng thuốc cũ",
                clinical_summary="Đau rát dạ dày cấp sau dùng thuốc. Kích hoạt rào cản an toàn dừng thuốc cũ.",
                ai_directive="BẮT BUỘC DỪNG CÁCH CŨ. Ngừng NSAID ngay lập tức.",
                medications_adjusted=["Ngưng thuốc kích ứng dạ dày"],
            )
        )
        p.last_updated = now_str
        return p

    def _apply_allergy_to_profile(self, current: PatientHealthProfile, now_str: str, message: str) -> PatientHealthProfile:
        p = current.model_copy(deep=True)
        p.active_diagnosis = "Dị ứng thuốc cấp tính (Nổi mề đay / Ban da)"
        p.overall_health_score = max(40, p.overall_health_score - 20)
        p.health_trend = "critical_alert"

        for organ in p.organs:
            if organ.id == "skin":
                organ.status = "adverse_reaction"
                organ.health_score = 40
                organ.pain_level = 5
                organ.inflammation_level = "severe"
                organ.symptoms = ["Nổi ban đỏ", "Ngứa ngáy rát da"]
                organ.warning = "CẢNH BÁO DỊ ỨNG THUỐC: Dừng ngay để ngừa sốc phản vệ!"
                organ.is_adverse_reaction = True

        p.safe_guardrail_alert = SafeGuardrailAlert(
            alert_level="danger",
            title="DỪNG THUỐC KHẨN CẤP: Dấu hiệu dị ứng thuốc",
            cause_identified="Phản ứng nổi ban đỏ và ngứa ngáy sau dùng thuốc.",
            contraindicated_item="Toàn bộ thuốc mới bắt đầu uống",
            required_action="NGỪNG NGAY LẬP TỨC toàn bộ liều thuốc kế tiếp.",
            alternative_recommendation="Theo dõi sát hô hấp. Nếu khó thở hoặc sưng phù mặt, gọi 115 ngay.",
            seek_emergency=False,
        )

        p.timeline.append(
            RecoveryTimelinePoint(
                id=f"t{len(p.timeline)+1}",
                timestamp=now_str,
                phase="adverse_event_escalation",
                title="Phát hiện dị ứng thuốc",
                trigger_message=message,
                health_score=p.overall_health_score,
                status_label="Dị ứng thuốc cấp",
                clinical_summary="Nổi ban da và ngứa ngáy sau dùng thuốc.",
                ai_directive="Ngừng thuốc ngay lập tức, theo dõi đường thở.",
                medications_adjusted=["Ngưng thuốc gây dị ứng"],
            )
        )
        p.last_updated = now_str
        return p

    def _apply_escalation_to_profile(self, current: PatientHealthProfile, now_str: str, message: str) -> PatientHealthProfile:
        p = current.model_copy(deep=True)
        p.active_diagnosis = "Bệnh tiến triển nặng - Sốt cao / Bội nhiễm hô hấp"
        p.overall_health_score = max(35, p.overall_health_score - 30)
        p.health_trend = "critical_alert"
        p.vitals.temperature_celsius = 39.5
        p.vitals.heart_rate_bpm = 108
        p.vitals.spo2_percent = 95

        for organ in p.organs:
            if organ.id in ["head", "lungs"]:
                organ.status = "critical"
                organ.health_score = 45
                organ.pain_level = 6
                organ.inflammation_level = "severe"
                organ.warning = "TRIỆU CHỨNG TIẾN TRIỂN NẶNG VƯỢT NGƯỠNG ĐIỀU TRỊ TẠI NHÀ"

        p.safe_guardrail_alert = SafeGuardrailAlert(
            alert_level="critical",
            title="HẠN CHẾ CÁCH CŨ: Dừng tự điều trị tại nhà, cần tới bệnh viện",
            cause_identified="Bệnh nhân sốt cao kịch phát hoặc khó thở tăng nặng.",
            contraindicated_item="Tiếp tục nằm nhà uống thuốc hạ sốt đơn thuần",
            required_action="ĐẾN CƠ SỞ Y TẾ HOẶC PHÒNG CẤP CỨU GẦN NHẤT ĐỂ ĐƯỢC BÁC SĨ KHÁM TRỰC TIẾP",
            alternative_recommendation="Chườm mát vùng cổ nách bẹn, chuẩn bị hồ sơ y tế và di chuyển an toàn.",
            seek_emergency=True,
        )

        p.timeline.append(
            RecoveryTimelinePoint(
                id=f"t{len(p.timeline)+1}",
                timestamp=now_str,
                phase="adverse_event_escalation",
                title="Tiến triển nặng vượt ngưỡng",
                trigger_message=message,
                health_score=p.overall_health_score,
                status_label="Báo động nguy kịch",
                clinical_summary="Sốt cao tiến triển, nguy cơ biến chứng hô hấp.",
                ai_directive="Dừng tự điều trị tại nhà, di chuyển đến viện ngay.",
                medications_adjusted=[],
            )
        )
        p.last_updated = now_str
        return p

    def _apply_recovery_to_profile(self, current: PatientHealthProfile, now_str: str, message: str) -> PatientHealthProfile:
        p = current.model_copy(deep=True)
        p.active_diagnosis = "Giai đoạn hồi phục sau cảm cúm"
        p.overall_health_score = min(96, max(90, p.overall_health_score + 20))
        p.health_trend = "improving"
        p.vitals.temperature_celsius = 36.8
        p.vitals.overall_pain_level = 0
        p.vitals.heart_rate_bpm = 74

        for organ in p.organs:
            if organ.id in ["head", "ent", "lungs", "spine_joints"]:
                organ.status = "normal"
                organ.health_score = 96
                organ.pain_level = 0
                organ.inflammation_level = "none"
                organ.symptoms = []
                organ.clinical_notes = "Đã thuyên giảm hoàn toàn, không còn triệu chứng khó chịu."
                organ.warning = None

        if "Paracetamol 500mg" in p.active_medications:
            p.active_medications.remove("Paracetamol 500mg")
            p.discontinued_medications.append("Paracetamol 500mg (Dừng do đã cắt sốt & hết đau đầu)")

        p.safe_guardrail_alert = None
        p.clinical_directives = [
            "Ngừng dùng thuốc giảm đau Paracetamol khi đã hết triệu chứng",
            "Tiếp tục uống nhiều nước và vệ sinh mũi họng bằng nước muối sinh lý",
            "Bổ sung vitamin, nghỉ ngơi hợp lý để duy trì thể trạng tối ưu",
        ]

        p.timeline.append(
            RecoveryTimelinePoint(
                id=f"t{len(p.timeline)+1}",
                timestamp=now_str,
                phase="improved_recovering",
                title="Thuyên giảm triệu chứng & Hồi phục",
                trigger_message=message,
                health_score=p.overall_health_score,
                status_label="Hồi phục xuất sắc (96%)",
                clinical_summary="Hết sốt, hết đau đầu sổ mũi, thể trạng phục hồi tốt.",
                ai_directive="Khuyên ngừng thuốc hạ sốt, duy trì lối sống lành mạnh.",
                medications_adjusted=["Ngừng Paracetamol khi hết triệu chứng"],
            )
        )
        p.last_updated = now_str
        return p


patient_health_twin_service = PatientHealthTwinService()
