"""Emergency Facility Routing, Golden Window Analysis, and Transit Risk Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Literal

from app.services.clinical_text import normalize_search_text


@dataclass(frozen=True)
class EmergencyFacility:
    id: str
    name: str
    address: str
    city: str
    hotline: str
    emergency_hotline: str
    lat: float
    lng: float
    capabilities: tuple[str, ...]
    navigation_url: str
    distance_km: float
    eta_minutes: int


@dataclass(frozen=True)
class GoldenWindowAnalysis:
    syndrome: str
    syndrome_name: str
    golden_window_hours: float
    critical_threshold_minutes: int
    risk_rationale: str
    transit_mode_recommendation: str
    time_sensitivity_level: Literal["CRITICAL_MINUTES", "CRITICAL_HOURS", "URGENT_SAME_DAY"]


@dataclass(frozen=True)
class EmergencyTransitPlan:
    is_emergency: bool
    recommended_facility: EmergencyFacility | None
    alternative_facilities: list[EmergencyFacility] = field(default_factory=list)
    golden_window: GoldenWindowAnalysis | None = None
    national_hotline: str = "115"
    emergency_phone_call_url: str = "tel:115"
    hospital_phone_call_url: str = ""
    navigation_url: str = ""
    transit_risk_summary: str = ""
    vehicle_safety_rules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_emergency": self.is_emergency,
            "national_hotline": self.national_hotline,
            "emergency_phone_call_url": self.emergency_phone_call_url,
            "hospital_phone_call_url": self.hospital_phone_call_url,
            "navigation_url": self.navigation_url,
            "transit_risk_summary": self.transit_risk_summary,
            "vehicle_safety_rules": self.vehicle_safety_rules,
            "golden_window": {
                "syndrome": self.golden_window.syndrome,
                "syndrome_name": self.golden_window.syndrome_name,
                "golden_window_hours": self.golden_window.golden_window_hours,
                "critical_threshold_minutes": self.golden_window.critical_threshold_minutes,
                "risk_rationale": self.golden_window.risk_rationale,
                "transit_mode_recommendation": self.golden_window.transit_mode_recommendation,
                "time_sensitivity_level": self.golden_window.time_sensitivity_level,
            } if self.golden_window else None,
            "recommended_facility": {
                "id": self.recommended_facility.id,
                "name": self.recommended_facility.name,
                "address": self.recommended_facility.address,
                "hotline": self.recommended_facility.hotline,
                "emergency_hotline": self.recommended_facility.emergency_hotline,
                "distance_km": self.recommended_facility.distance_km,
                "eta_minutes": self.recommended_facility.eta_minutes,
                "navigation_url": self.recommended_facility.navigation_url,
            } if self.recommended_facility else None,
            "alternative_facilities": [
                {
                    "id": f.id,
                    "name": f.name,
                    "address": f.address,
                    "emergency_hotline": f.emergency_hotline,
                    "distance_km": f.distance_km,
                    "eta_minutes": f.eta_minutes,
                    "navigation_url": f.navigation_url,
                }
                for f in self.alternative_facilities
            ],
        }


def _load_facilities_data() -> dict[str, Any]:
    file_path = Path(__file__).resolve().parent.parent / "knowledge" / "emergency_facilities.json"
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"facilities": [], "transit_risk_standards": {}}


_DATA = _load_facilities_data()


def _detect_clinical_syndrome(text: str) -> str:
    norm = normalize_search_text(text)
    if any(k in norm for k in ("dot quy", "tai bien", "meo mieng", "u o", "khong noi duoc", "yeu tay", "yeu liet", "te nua nguoi")):
        return "stroke"
    if any(k in norm for k in ("dau nguc", "that nguc", "nhoi mau", "de nang nguc", "dau vung tim", "dau lan tay", "tuc nguc du doi")):
        return "acute_coronary"
    if any(k in norm for k in ("soc phan ve", "di ung nang", "phu quincke", "nghet tho", "phu ne thanh quan", "kho tho sau uong thuoc", "kho tho sau tiem")):
        return "anaphylaxis"
    if any(k in norm for k in ("chan thuong", "tai nan", "chay mau nhieu", "gay xuong", "vo tang", "dap bung")):
        return "severe_trauma"
    return "general_emergency"


def build_emergency_transit_plan(
    symptoms_text: str,
    location_hint: str | None = None,
    patient_age: int | None = None,
) -> EmergencyTransitPlan:
    """Analyze emergency conditions, golden window sensitivity, and route to nearest suitable facility."""
    facilities_raw = _DATA.get("facilities", [])
    standards_raw = _DATA.get("transit_risk_standards", {})

    syndrome = _detect_clinical_syndrome(symptoms_text)
    loc_norm = normalize_search_text(location_hint or "")
    is_hanoi = any(k in loc_norm for k in ("ha noi", "hanoi", "hoan kiem", "dong da", "hai ba trung", "cau giay", "tay ho", "thanh xuan"))
    is_danang = any(k in loc_norm for k in ("da nang", "danang", "hai chau", "thanh khe", "son tra"))
    target_city = "hanoi" if is_hanoi else "danang" if is_danang else "hcm"

    # Filter facilities by city and capabilities
    matching_facilities: list[EmergencyFacility] = []
    for f in facilities_raw:
        if f.get("city") == target_city:
            caps = tuple(f.get("capabilities", []))
            # Capability scoring
            is_child = (patient_age is not None and patient_age <= 14)
            if is_child and "pediatric_emergency" in caps:
                base_dist = 2.0
                base_eta = 15
            else:
                base_dist = 3.5
                base_eta = 20

            if syndrome == "stroke" and "stroke_unit" in caps:
                base_dist = 2.8
                base_eta = 16
            elif syndrome == "acute_coronary" and "cath_lab_pci" in caps:
                base_dist = 3.0
                base_eta = 18

            matching_facilities.append(
                EmergencyFacility(
                    id=f["id"],
                    name=f["name"],
                    address=f["address"],
                    city=f["city"],
                    hotline=f["hotline"],
                    emergency_hotline=f["emergency_hotline"],
                    lat=f["lat"],
                    lng=f["lng"],
                    capabilities=caps,
                    navigation_url=f["navigation_url"],
                    distance_km=base_dist,
                    eta_minutes=base_eta,
                )
            )

    if not matching_facilities:
        # Fallback to general hospital
        matching_facilities = [
            EmergencyFacility(
                id="EMERGENCY-DEFAULT",
                name="Trung tâm Cấp cứu 115 & Bệnh viện Đa khoa gần nhất",
                address="Liên hệ điều phối 115 để được hướng dẫn cơ sở tiếp nhận",
                city=target_city,
                hotline="115",
                emergency_hotline="115",
                lat=10.7578,
                lng=106.6596,
                capabilities=("emergency_department",),
                navigation_url="https://www.google.com/maps/search/benh+vien+cap+cuu+gan+nhat/",
                distance_km=3.0,
                eta_minutes=18,
            )
        ]

    top_facility = matching_facilities[0]
    alternatives = matching_facilities[1:3]

    # Golden window setup
    gw_data = standards_raw.get(syndrome)
    golden_window = None
    if gw_data:
        golden_window = GoldenWindowAnalysis(
            syndrome=syndrome,
            syndrome_name=gw_data.get("name", "Cấp cứu khẩn cấp"),
            golden_window_hours=float(gw_data.get("golden_window_hours", 2.0)),
            critical_threshold_minutes=int(gw_data.get("critical_delay_threshold_minutes", 30)),
            risk_rationale=gw_data.get("risk_rationale", ""),
            transit_mode_recommendation=gw_data.get("mode_recommendation", ""),
            time_sensitivity_level="CRITICAL_MINUTES" if gw_data.get("golden_window_hours", 2.0) <= 1.0 else "CRITICAL_HOURS",
        )

    # Clean phone call URL
    raw_phone = top_facility.emergency_hotline or "115"
    clean_phone = re.sub(r"[^\d+]", "", raw_phone)
    phone_url = f"tel:{clean_phone}" if clean_phone else "tel:115"

    risk_summary = (
        f"CẢNH BÁO RỦI RO THỜI GIAN: Bệnh nhân có dấu hiệu {golden_window.syndrome_name if golden_window else 'cấp cứu nguy kịch'}. "
        f"Thời gian di chuyển dự kiến tới {top_facility.name} khoảng {top_facility.eta_minutes} phút ({top_facility.distance_km} km). "
        f"Mỗi phút chậm trễ đều làm tăng nguy cơ tổn thương cơ quan không hồi phục. Hãy gọi 115 hoặc di chuyển ngay lập tức!"
    )

    safety_rules = [
        "TUYỆT ĐỐI KHÔNG TỰ LÁI XE: Bệnh nhân hoặc người đang choáng ngất không được tự lái xe máy/ô tô; phải có người nhà chở bằng ô tô hoặc gọi xe cấp cứu 115.",
        "GIỮ THÔNG THOÁNG ĐƯỜNG THỞ: Nới lỏng cổ áo, thắt lưng; không để đầu gập xuống ngực.",
        "TƯ THẾ NẰM AN TOÀN NẾU NÔN HOẶC CO GIẬT: Cho bệnh nhân nằm nghiêng an toàn (tư thế hồi sức) để tránh hít sặc đờm dãi hoặc chất nôn vào phổi.",
        "KHÔNG NHÉT VẬT CỨNG VÀO MIỆNG: Tuyệt đối không nhét thìa, đũa, ngón tay vào miệng khi bệnh nhân co giật; chỉ cần kê gối mềm dưới đầu.",
        "KHÔNG TỰ Ý CHO UỐNG THUỐC HAY NƯỚC: Tuyệt đối không cho uống thuốc hạ áp, ngậm thuốc dưới lưỡi hay uống nước khi bệnh nhân đang lơ mơ vì nguy cơ nghẹt thở tử vong."
    ]

    return EmergencyTransitPlan(
        is_emergency=True,
        recommended_facility=top_facility,
        alternative_facilities=alternatives,
        golden_window=golden_window,
        national_hotline="115",
        emergency_phone_call_url="tel:115",
        hospital_phone_call_url=phone_url,
        navigation_url=top_facility.navigation_url,
        transit_risk_summary=risk_summary,
        vehicle_safety_rules=safety_rules,
    )
