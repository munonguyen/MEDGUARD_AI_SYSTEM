"""Pre-Hospital En-Route Physical Inspection and Rapid Triage Engine.

Analyzes non-instrumented external physical signs reported by family or patient
while traveling in vehicle/taxi/ambulance without medical monitors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from app.services.clinical_text import normalize_search_text


@dataclass(frozen=True)
class PreHospitalPhysicalSign:
    system: str  # consciousness, airway_breathing, circulation, neuromuscular
    sign_name: str
    severity: str  # CRITICAL, HIGH, MODERATE
    clinical_meaning: str


@dataclass(frozen=True)
class EnRouteTriageAssessment:
    is_en_route: bool
    detected_signs: list[PreHospitalPhysicalSign]
    consciousness_avpu: str  # Alert, Voice, Pain, Unresponsive
    pre_hospital_impression: str
    immediate_actions_in_vehicle: list[str]
    prohibited_actions_in_vehicle: list[str]
    handover_notes_for_er: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_en_route": self.is_en_route,
            "consciousness_avpu": self.consciousness_avpu,
            "pre_hospital_impression": self.pre_hospital_impression,
            "immediate_actions_in_vehicle": self.immediate_actions_in_vehicle,
            "prohibited_actions_in_vehicle": self.prohibited_actions_in_vehicle,
            "handover_notes_for_er": self.handover_notes_for_er,
            "detected_signs": [
                {
                    "system": s.system,
                    "sign_name": s.sign_name,
                    "severity": s.severity,
                    "clinical_meaning": s.clinical_meaning,
                }
                for s in self.detected_signs
            ],
        }


def is_en_route_statement(text: str) -> bool:
    norm = normalize_search_text(text)
    markers = (
        "dang tren xe",
        "dang di cap cuu",
        "dang di vien",
        "dang tren taxi",
        "dang cho di",
        "tren duong di",
        "tren duong den vien",
        "dang tren duong",
        "tren xe cap cuu",
        "tren xe",
        "sap den vien",
        "con 5 phut",
        "con 10 phut",
        "dang chay den",
    )
    return any(m in norm for m in markers)


def evaluate_enroute_physical_signs(text: str) -> EnRouteTriageAssessment:
    """Analyze observable physical signs from layman descriptions during emergency transit."""
    norm = normalize_search_text(text)
    signs: list[PreHospitalPhysicalSign] = []
    avpu = "Alert"

    # 1. Tri giác (Consciousness - AVPU)
    if any(k in norm for k in ("bat tinh", "hon me", "khong phan ung", "goi khong biet", "khong dap ung")):
        avpu = "Unresponsive"
        signs.append(PreHospitalPhysicalSign("consciousness", "Hôn mê / Mất tri giác hoàn toàn (U)", "CRITICAL", "Nguy cơ mất phản xạ bảo vệ đường thở, tụt lưỡi gây ngạt thở"))
    elif any(k in norm for k in ("veo moi biet", "dau moi nhan mat", "phai bam vao moi cu dong")):
        avpu = "Pain"
        signs.append(PreHospitalPhysicalSign("consciousness", "Chỉ đáp ứng khi kích thích đau (P)", "CRITICAL", "Ức chế thần kinh trung ương mức độ sâu"))
    elif any(k in norm for k in ("lo mo", "goi moi mo mat", "u o", "buon ngu khong mo noi mat")):
        avpu = "Voice"
        signs.append(PreHospitalPhysicalSign("consciousness", "Lơ mơ / Đáp ứng chậm với lời nói (V)", "HIGH", "Thiếu máu não hoặc suy hô hấp tiến triển"))
    elif any(k in norm for k in ("me sang", "noi nham", "lam nham", "loan than")):
        avpu = "Voice"
        signs.append(PreHospitalPhysicalSign("consciousness", "Rối loạn tri giác / Mê sảng", "HIGH", "Thiếu oxy não hoặc nhiễm trùng huyết / rối loạn chuyển hóa nặng"))

    # 2. Hô hấp & Đường thở (Airway & Breathing)
    if any(k in norm for k in ("sui bot mep", "bot mep", "nghieng rang", "can luoi", "can rang")):
        signs.append(PreHospitalPhysicalSign("airway_breathing", "Sùi bọt mép / Cắn răng co giật", "CRITICAL", "Tắc nghẽn đường thở do tăng tiết và co cứng cơ hầu họng"))
    if any(k in norm for k in ("tho rit", "tho khok khe", "nghet tho", "tho ngay bat thuong")):
        signs.append(PreHospitalPhysicalSign("airway_breathing", "Thở rít thanh quản / Khò khè tắc nghẽn", "CRITICAL", "Phù nề thanh môn hoặc dị vật / tụt lưỡi đè đường thở"))
    if any(k in norm for k in ("tim moi", "tim tai", "dau ngon tay tim", "moi tai nhot")):
        signs.append(PreHospitalPhysicalSign("airway_breathing", "Tím tái môi và đầu chi (Cyanosis)", "CRITICAL", "Suy hô hấp thiếu oxy máu nặng (SpO2 tụt thấp)"))
    if any(k in norm for k in ("co keo", "rut lom nguc", "tho doc", "tho gap", "tho nhanh nong")):
        signs.append(PreHospitalPhysicalSign("airway_breathing", "Co kéo cơ hô hấp phụ / Thở gắng sức", "HIGH", "Kiệt sức cơ hô hấp, đe dọa ngừng thở"))

    # 3. Tuần hoàn (Circulation)
    if any(k in norm for k in ("va mo hoi lanh", "lanh toat", "da tai nhot", "nguoi lanh run")):
        signs.append(PreHospitalPhysicalSign("circulation", "Vã mồ hôi lạnh / Da nhớp lạnh tái nhợt", "CRITICAL", "Dấu hiệu sốc tim hoặc sốc giảm thể tích / tụt huyết áp nghiêm trọng"))
    if any(k in norm for k in ("khong bat duoc mach", "mach yeu", "mach nhanh nho")):
        signs.append(PreHospitalPhysicalSign("circulation", "Mạch quay yếu hoặc không bắt được", "CRITICAL", "Huyết áp tâm thu có thể dưới 80 mmHg, nguy cơ trụy mạch"))

    # 4. Thần kinh & Vận động (Neuromuscular)
    if any(k in norm for k in ("co giat", "giat giat", "co cung", "tron mat")):
        signs.append(PreHospitalPhysicalSign("neuromuscular", "Cơn co giật toàn thể / Co cứng cơ", "CRITICAL", "Cơn động kinh hoặc xuất huyết não, tổn thương thần kinh cấp"))
    if any(k in norm for k in ("meo mieng", "lech mat", "yeu mot ben", "liet tay", "roi coc")):
        signs.append(PreHospitalPhysicalSign("neuromuscular", "Dấu hiệu khiếm khuyết thần kinh khu trú (F.A.S.T)", "CRITICAL", "Dấu hiệu đột quỵ thiếu máu não hoặc xuất huyết não cấp"))
    if any(k in norm for k in ("non oi", "non vot", "oi mua")):
        signs.append(PreHospitalPhysicalSign("gastrointestinal", "Nôn vọt / Nôn ói liên tục", "HIGH", "Tăng áp lực nội sọ hoặc kích thích phúc mạc, nguy cơ sặc chất nôn"))

    # Synthesize impression & actionable advice in vehicle
    is_critical = any(s.severity == "CRITICAL" for s in signs)
    if "stroke" in norm or any("F.A.S.T" in s.sign_name for s in signs):
        impression = "Theo dõi đột quỵ cấp (Tai biến mạch máu não) có biểu hiện thần kinh khu trú trên đường di chuyển."
    elif any("co giat" in s.sign_name.lower() for s in signs):
        impression = "Cơn co giật cấp tính nghi do động kinh, tai biến mạch máu não hoặc rối loạn chuyển hóa nặng."
    elif any("Cyanosis" in s.clinical_meaning or "Thở rít" in s.sign_name for s in signs):
        impression = "Hội chứng suy hô hấp cấp nặng / Tắc nghẽn đường thở đe dọa ngạt thở."
    elif any("Vã mồ hôi lạnh" in s.sign_name for s in signs):
        impression = "Hội chứng trụy tim mạch / Sốc cấp (nghi nhồi máu cơ tim hoặc sốc tim)."
    else:
        impression = "Tình trạng cấp cứu tiến triển có suy giảm chức năng sinh tồn trên đường chuyển viện."

    immediate_actions = []
    prohibited_actions = []

    # Safe positioning in vehicle
    if avpu in ("Pain", "Unresponsive", "Voice") or any("co giat" in s.sign_name.lower() or "Nôn" in s.sign_name for s in signs):
        immediate_actions.append("ĐẶT BỆNH NHÂN NẰM NGHIÊNG AN TOÀN (Tư thế hồi sức bên trái): Đầu nghiêng sang một bên để đờm nhớt và chất nôn tự chảy ra ngoài, chống sặc vào khí quản.")
        immediate_actions.append("NỚI LỎNG CỔ ÁO, KHĂN QUÀNG, THẮT LƯNG: Giúp lồng ngực di động dễ dàng và đường thở không bị chèn ép.")
    elif any("Cyanosis" in s.clinical_meaning or "Thở gắng sức" in s.sign_name for s in signs):
        immediate_actions.append("TƯ THẾ NỬA NẰM NỬA NGỒI (FOWLER 45 ĐỘ): Kê gối hoặc đỡ lưng bệnh nhân ngồi tựa góc 45 độ để giảm ứ máu ở phổi và thở dễ hơn.")

    if any("co giat" in s.sign_name.lower() for s in signs):
        immediate_actions.append("KÊ VẬT MỀM DƯỚI ĐẦU: Dùng áo khoác hoặc gối mềm lót dưới đầu để tránh chấn thương sọ não do va đập sàn xe.")
        prohibited_actions.append("TUYỆT ĐỐI KHÔNG NHÉT BẤT KỲ VẬT CỨNG NÀO VÀO MIỆNG (không đút thìa, đũa, chanh, ngón tay): Hành động này có thể làm gãy răng, tụt vào khí quản gây nghẹt thở tử vong.")
        prohibited_actions.append("KHÔNG ĐÈ ÉP GIỮ CHẶT CHÂN TAY ĐANG CO GIẬT: Có thể gây gãy xương hoặc trật khớp; chỉ dọn dẹp vật sắc nhọn xung quanh.")

    prohibited_actions.append("TUYỆT ĐỐI KHÔNG CHO UỐNG NƯỚC HOẶC UỐNG THUỐC TRÊN XE: Khi tri giác giảm hoặc đang ho/co giật, nước sẽ tràn vào phổi gây viêm phổi hít tắc thở.")
    prohibited_actions.append("KHÔNG CẠO GIÓ, CẮT LỂ, CHÂM KIM 10 ĐẦU NGÓN TAY: Đây là phản khoa học làm mất thời gian giờ vàng và tăng nguy cơ nhiễm trùng máu.")

    handover_notes = [
        f"Ghi nhận mốc thời gian xuất hiện triệu chứng đầu tiên: rất quan trọng để bác sĩ tính giờ vàng.",
        f"Mức tri giác hiện tại (AVPU): {avpu}.",
        f"Mang theo vỏ thuốc hoặc đơn thuốc bệnh nhân đang dùng hàng ngày để bàn giao ngay khi đến phòng cấp cứu."
    ]

    return EnRouteTriageAssessment(
        is_en_route=is_en_route_statement(text),
        detected_signs=signs,
        consciousness_avpu=avpu,
        pre_hospital_impression=impression,
        immediate_actions_in_vehicle=immediate_actions,
        prohibited_actions_in_vehicle=prohibited_actions,
        handover_notes_for_er=handover_notes,
    )
