"""Central Hybrid POI Hub for Emergency Facilities and GPP Pharmacies.

Manages centralized location registry with real-time operating hours verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
import json
from pathlib import Path
from typing import Any, Literal
import zoneinfo

from app.services.clinical_text import normalize_search_text


@dataclass(frozen=True)
class OperatingStatus:
    is_open: bool
    status_badge: Literal["OPEN_24_7", "OPEN_NOW", "CLOSING_SOON", "CLOSED"]
    status_label: str
    detail_text: str
    closes_at: str | None = None
    opens_at: str | None = None
    minutes_until_close: int | None = None


@dataclass(frozen=True)
class POIItem:
    id: str
    name: str
    poi_type: Literal["hospital_emergency", "pharmacy"]
    chain_or_dept: str
    address: str
    city: str
    district: str
    hotline: str
    emergency_or_direct_phone: str
    lat: float
    lng: float
    capabilities_or_services: list[str]
    operating_hours_raw: dict[str, Any]
    operating_status: OperatingStatus
    navigation_url: str


def _get_vietnam_time() -> datetime:
    """Return current time in Asia/Ho_Chi_Minh timezone (GMT+7)."""
    try:
        tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
        return datetime.now(tz)
    except Exception:
        # Fallback to local time if zoneinfo is not available
        return datetime.now()


def evaluate_operating_hours(
    operating_raw: dict[str, Any],
    check_time: datetime | None = None,
) -> OperatingStatus:
    """Evaluate whether a POI is open right now, closing soon, or closed."""
    now = check_time or _get_vietnam_time()
    current_time_val = now.time()

    is_24_7 = operating_raw.get("is_24_7", False)
    if is_24_7:
        return OperatingStatus(
            is_open=True,
            status_badge="OPEN_24_7",
            status_label="ĐANG MỞ CỬA (24/7)",
            detail_text="Hoạt động liên tục 24/7/365 — Luôn có nhân sự trực",
        )

    open_str = operating_raw.get("open", "07:00")
    close_str = operating_raw.get("close", "22:00")

    try:
        open_parts = [int(p) for p in open_str.split(":")]
        close_parts = [int(p) for p in close_str.split(":")]
        open_time = time(open_parts[0], open_parts[1])
        close_time = time(close_parts[0], close_parts[1])
    except Exception:
        open_time = time(7, 0)
        close_time = time(22, 0)

    now_minutes = current_time_val.hour * 60 + current_time_val.minute
    open_minutes = open_time.hour * 60 + open_time.minute
    close_minutes = close_time.hour * 60 + close_time.minute

    if open_minutes <= now_minutes <= close_minutes:
        diff_minutes = close_minutes - now_minutes
        if diff_minutes <= 30:
            return OperatingStatus(
                is_open=True,
                status_badge="CLOSING_SOON",
                status_label=f"SẮP ĐÓNG CỬA (Còn {diff_minutes} phút)",
                detail_text=f"Đóng cửa lúc {close_str}. Vui lòng liên hệ trước qua điện thoại.",
                closes_at=close_str,
                minutes_until_close=diff_minutes,
            )
        hours_left = diff_minutes // 60
        mins_left = diff_minutes % 60
        time_left_str = f"{hours_left}h {mins_left}p" if hours_left > 0 else f"{mins_left} phút"
        return OperatingStatus(
            is_open=True,
            status_badge="OPEN_NOW",
            status_label="ĐANG MỞ CỬA",
            detail_text=f"Mở cửa từ {open_str} - {close_str} (Còn hoạt động {time_left_str})",
            closes_at=close_str,
            minutes_until_close=diff_minutes,
        )

    return OperatingStatus(
        is_open=False,
        status_badge="CLOSED",
        status_label="ĐÃ ĐÓNG CỬA",
        detail_text=f"Đã hết giờ phục vụ ({open_str} - {close_str}). Mở cửa lại lúc {open_str} sáng mai.",
        opens_at=open_str,
    )


class HybridPoiHub:
    """Central repository and discovery engine for Emergency and Pharmacy POIs."""

    def __init__(self, registry_file: Path | None = None) -> None:
        self.registry_file = (
            registry_file
            or Path(__file__).resolve().parent.parent / "knowledge" / "hybrid_poi_registry.json"
        )
        self._raw_data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.registry_file.exists():
            try:
                return json.loads(self.registry_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"emergency_facilities": [], "pharmacies": [], "traffic_corridors": {}}

    def list_pois(
        self,
        poi_type: Literal["emergency", "pharmacy", "all"] = "all",
        city: str | None = None,
        check_time: datetime | None = None,
    ) -> list[POIItem]:
        """List and evaluate real-time open status for registered POIs."""
        results: list[POIItem] = []
        city_norm = (city or "").lower().strip()

        # 1. Emergency Facilities
        if poi_type in ("emergency", "all"):
            for ef in self._raw_data.get("emergency_facilities", []):
                if city_norm and ef.get("city") != city_norm:
                    continue
                op_status = evaluate_operating_hours(ef.get("operating_hours", {}), check_time)
                results.append(
                    POIItem(
                        id=ef["id"],
                        name=ef["name"],
                        poi_type="hospital_emergency",
                        chain_or_dept="Cấp cứu 115 / Bệnh viện",
                        address=ef["address"],
                        city=ef["city"],
                        district=ef.get("district", ""),
                        hotline=ef.get("hotline", "115"),
                        emergency_or_direct_phone=ef.get("emergency_hotline", "115"),
                        lat=float(ef["lat"]),
                        lng=float(ef["lng"]),
                        capabilities_or_services=list(ef.get("capabilities", [])),
                        operating_hours_raw=ef.get("operating_hours", {}),
                        operating_status=op_status,
                        navigation_url=ef.get("navigation_url", ""),
                    )
                )

        # 2. Pharmacies
        if poi_type in ("pharmacy", "all"):
            for ph in self._raw_data.get("pharmacies", []):
                if city_norm and ph.get("city") != city_norm:
                    continue
                op_status = evaluate_operating_hours(ph.get("operating_hours", {}), check_time)
                results.append(
                    POIItem(
                        id=ph["id"],
                        name=ph["name"],
                        poi_type="pharmacy",
                        chain_or_dept=ph.get("chain", "Nhà thuốc GPP"),
                        address=ph["address"],
                        city=ph["city"],
                        district=ph.get("district", ""),
                        hotline=ph.get("hotline", "1800 6928"),
                        emergency_or_direct_phone=ph.get("direct_phone", ph.get("hotline", "")),
                        lat=float(ph["lat"]),
                        lng=float(ph["lng"]),
                        capabilities_or_services=list(ph.get("services", [])),
                        operating_hours_raw=ph.get("operating_hours", {}),
                        operating_status=op_status,
                        navigation_url=ph.get("google_maps_url", ""),
                    )
                )

        return results

    def get_traffic_corridors(self, city: str) -> dict[str, Any]:
        """Retrieve real-time congestion corridor heuristics for given city."""
        corridors = self._raw_data.get("traffic_corridors", {})
        return corridors.get(city.lower(), corridors.get("hcm", {}))


# Global singleton instance
hub_instance = HybridPoiHub()
