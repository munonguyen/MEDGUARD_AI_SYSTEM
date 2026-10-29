"""Geoapify Live API Client for Dynamic Places Search, Geocoding, and Real-Time Routing.

Connects to Geoapify services using API key: 224447c8da3b4555a5380f31ddb56bf3
Provides dynamic hospital/pharmacy POI discovery and real-time turn-by-turn road routing.
"""

from __future__ import annotations

import logging
import os
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)

DEFAULT_GEOAPIFY_KEY = "224447c8da3b4555a5380f31ddb56bf3"


@dataclass(frozen=True)
class GeoapifyPlace:
    id: str
    name: str
    category: str
    address: str
    city: str
    lat: float
    lon: float
    distance_meters: float
    phone: str | None = None
    opening_hours: str | None = None
    datasource_raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeoapifyRouteStep:
    step_number: int
    instruction: str
    distance_meters: float
    time_seconds: float
    road_name: str | None = None


@dataclass(frozen=True)
class GeoapifyRouteResult:
    distance_meters: float
    distance_km: float
    duration_seconds: float
    eta_minutes: int
    steps: list[GeoapifyRouteStep]
    coordinates: list[tuple[float, float]]  # (lat, lon)


def translate_step_instruction(text: str, road: str | None = None) -> str:
    """Translates raw routing instructions into 100% natural Vietnamese instructions."""
    if not text:
        return f"Đi tiếp vào {road}." if (road and road != "Đoạn đường di chuyển") else "Tiếp tục di chuyển."
    t = text.strip()

    # Clean fake road names
    clean_road = road.strip() if road and road.strip() not in ("Đoạn đường di chuyển", "Unnamed road") else None

    if "destination is on the left" in t.lower():
        return "Bạn đã đến nơi. Cơ sở y tế nằm ở bên trái của bạn."
    if "destination is on the right" in t.lower():
        return "Bạn đã đến nơi. Cơ sở y tế nằm ở bên phải của bạn."
    if "destination" in t.lower():
        return "Điểm đến ở ngay phía trước."
    if "arrive" in t.lower():
        return f"Bạn đã đến nơi: {clean_road or 'Cơ sở y tế'}."

    m_round = re.search(r"take the (\d+)(?:st|nd|rd|th)? exit onto (.+)", t, re.IGNORECASE)
    if m_round:
        return f"Đi vào vòng xuyến, theo lối ra thứ {m_round.group(1)} vào {m_round.group(2).rstrip('.')}."
    if "enter the roundabout" in t.lower():
        return f"Đi vào vòng xuyến theo hướng {clean_road or 'tuyến đường'}."
    if "exit the roundabout" in t.lower():
        return f"Rời vòng xuyến vào {clean_road or 'tuyến đường tiếp theo'}."

    m_uturn = re.search(r"make a (?:left|right)?\s*u-turn(?: at (.+?))?(?: to stay on (.+))?\.?$", t, re.IGNORECASE)
    if m_uturn:
        at_st = m_uturn.group(1).rstrip(".") if m_uturn.group(1) else None
        stay_st = m_uturn.group(2).rstrip(".") if m_uturn.group(2) else None
        if at_st and stay_st:
            return f"Quay đầu xe (chữ U) tại {at_st} để tiếp tục trên {stay_st}."
        if at_st:
            return f"Quay đầu xe (chữ U) tại {at_st}."
        return "Quay đầu xe (chữ U) tại điểm mở dải phân cách."

    m_sharp_left = re.search(r"^turn sharp left(?: onto (.+))?\.?$", t, re.IGNORECASE)
    if m_sharp_left:
        r = m_sharp_left.group(1).rstrip(".") if m_sharp_left.group(1) else clean_road
        return f"Rẽ ngoặt sang trái vào {r}." if r else "Rẽ ngoặt sang trái."

    m_sharp_right = re.search(r"^turn sharp right(?: onto (.+))?\.?$", t, re.IGNORECASE)
    if m_sharp_right:
        r = m_sharp_right.group(1).rstrip(".") if m_sharp_right.group(1) else clean_road
        return f"Rẽ ngoặt sang phải vào {r}." if r else "Rẽ ngoặt sang phải."

    m_slight_left = re.search(r"^turn slight left(?: onto (.+))?\.?$", t, re.IGNORECASE)
    if m_slight_left:
        r = m_slight_left.group(1).rstrip(".") if m_slight_left.group(1) else clean_road
        return f"Chếch nhẹ sang trái vào {r}." if r else "Chếch nhẹ sang trái."

    m_slight_right = re.search(r"^turn slight right(?: onto (.+))?\.?$", t, re.IGNORECASE)
    if m_slight_right:
        r = m_slight_right.group(1).rstrip(".") if m_slight_right.group(1) else clean_road
        return f"Chếch nhẹ sang phải vào {r}." if r else "Chếch nhẹ sang phải."

    m_tr = re.search(r"^turn right(?: onto (.+))?\.?$", t, re.IGNORECASE)
    if m_tr:
        r = m_tr.group(1).rstrip(".") if m_tr.group(1) else clean_road
        return f"Rẽ phải vào {r}." if r else "Rẽ phải."

    m_tl = re.search(r"^turn left(?: onto (.+))?\.?$", t, re.IGNORECASE)
    if m_tl:
        r = m_tl.group(1).rstrip(".") if m_tl.group(1) else clean_road
        return f"Rẽ trái vào {r}." if r else "Rẽ trái."

    m_stay = re.search(r"^keep (right|left) to stay on (.+)\.?$", t, re.IGNORECASE)
    if m_stay:
        side = "bên phải" if m_stay.group(1).lower() == "right" else "bên trái"
        return f"Đi sát làn {side} để tiếp tục trên {m_stay.group(2).rstrip('.')}."

    m_kr = re.search(r"^keep right(?: onto (.+))?\.?$", t, re.IGNORECASE)
    if m_kr:
        r = m_kr.group(1).rstrip(".") if m_kr.group(1) else clean_road
        return f"Đi sát làn bên phải vào {r}." if r else "Đi sát làn bên phải."

    m_kl = re.search(r"^keep left(?: onto (.+))?\.?$", t, re.IGNORECASE)
    if m_kl:
        r = m_kl.group(1).rstrip(".") if m_kl.group(1) else clean_road
        return f"Đi sát làn bên trái vào {r}." if r else "Đi sát làn bên trái."

    m_head = re.search(r"^head (northeast|northwest|southeast|southwest|north|south|east|west)(?: on (.+))?\.?$", t, re.IGNORECASE)
    if m_head:
        dirs = {
            "northeast": "hướng Đông Bắc", "northwest": "hướng Tây Bắc",
            "southeast": "hướng Đông Nam", "southwest": "hướng Tây Nam",
            "north": "hướng Bắc", "south": "hướng Nam", "east": "hướng Đông", "west": "hướng Tây"
        }
        dn = dirs.get(m_head.group(1).lower(), m_head.group(1))
        r = m_head.group(2).rstrip(".") if m_head.group(2) else clean_road
        return f"Đi thẳng về {dn}{(' trên ' + r) if r else ''}."

    m_drive = re.search(r"^drive (northeast|northwest|southeast|southwest|north|south|east|west)(?: on (.+))?\.?$", t, re.IGNORECASE)
    if m_drive:
        dirs = {
            "northeast": "hướng Đông Bắc", "northwest": "hướng Tây Bắc",
            "southeast": "hướng Đông Nam", "southwest": "hướng Tây Nam",
            "north": "phía Bắc", "south": "phía Nam", "east": "phía Đông", "west": "phía Tây"
        }
        dn = dirs.get(m_drive.group(1).lower(), m_drive.group(1))
        r = m_drive.group(2).rstrip(".") if m_drive.group(2) else clean_road
        return f"Đi thẳng về {dn}{(' trên ' + r) if r else ''}."

    m_cont = re.search(r"^continue(?: straight)?(?: onto (.+))?\.?$", t, re.IGNORECASE)
    if m_cont:
        r = m_cont.group(1).rstrip(".") if m_cont.group(1) else clean_road
        return f"Tiếp tục đi thẳng trên {r}." if r else "Tiếp tục đi thẳng."

    m_ramp = re.search(r"stay straight to take the (.+) ramp\.?$", t, re.IGNORECASE)
    if m_ramp:
        return f"Đi thẳng lên đường dẫn {m_ramp.group(1).rstrip('.')}."

    # Strip any dangling "vào Đoạn đường di chuyển"
    res = t.replace("vào Đoạn đường di chuyển", "").strip()
    return res


class GeoapifyClient:
    """HTTP Client for Geoapify Places, Geocoding, and Routing APIs."""

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 7.0) -> None:
        self.api_key = api_key or os.getenv("GEOAPIFY_API_KEY", DEFAULT_GEOAPIFY_KEY)
        self.timeout = timeout_seconds

    def geocode(self, query_text: str) -> tuple[float, float, str] | None:
        """Geocode address or district string to (lat, lon, formatted_address)."""
        if not query_text or not query_text.strip():
            return None

        # Normalize Vietnamese city abbreviations for Nominatim OSM
        clean_text = query_text.strip()
        clean_lower = clean_text.lower()
        if any(k in clean_lower for k in ("tp.hcm", "tphcm", "tp hcm", "hồ chí minh", "ho chi minh")):
            # Remove abbreviations and append standard city name
            for k in ("tp.hcm", "tphcm", "tp hcm", "tp. hcm"):
                clean_text = clean_text.replace(k, "").replace(k.upper(), "")
            clean_text = f"{clean_text.strip(' ,')}, Ho Chi Minh City, Vietnam"
        elif any(k in clean_lower for k in ("hà nội", "ha noi", "hn")):
            for k in ("hà nội", "ha noi", "hn"):
                clean_text = clean_text.replace(k, "").replace(k.upper(), "")
            clean_text = f"{clean_text.strip(' ,')}, Hanoi, Vietnam"
        elif any(k in clean_lower for k in ("đà nẵng", "da nang", "đn")):
            for k in ("đà nẵng", "da nang", "đn"):
                clean_text = clean_text.replace(k, "").replace(k.upper(), "")
            clean_text = f"{clean_text.strip(' ,')}, Da Nang, Vietnam"

        encoded = urllib.parse.quote(clean_text)
        url = f"https://api.geoapify.com/v1/geocode/search?text={encoded}&limit=1&apiKey={self.api_key}"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    features = data.get("features", [])
                    if features:
                        props = features[0].get("properties", {})
                        coords = features[0].get("geometry", {}).get("coordinates", [])
                        if len(coords) >= 2:
                            lon, lat = float(coords[0]), float(coords[1])
                            formatted = props.get("formatted", query_text)
                            return lat, lon, formatted
        except Exception as e:
            logger.warning(f"Geoapify geocode failed for '{query_text}': {e}")
        return None

    def search_nearby_places(
        self,
        lat: float,
        lon: float,
        category: Literal["healthcare.hospital", "healthcare.pharmacy", "healthcare.clinic"] = "healthcare.hospital",
        radius_meters: int = 5000,
        limit: int = 10,
    ) -> list[GeoapifyPlace]:
        """Query live nearby healthcare POIs (hospitals or pharmacies) around coordinates."""
        url = (
            f"https://api.geoapify.com/v2/places"
            f"?categories={category}"
            f"&filter=circle:{lon},{lat},{radius_meters}"
            f"&bias=proximity:{lon},{lat}"
            f"&limit={limit}"
            f"&apiKey={self.api_key}"
        )

        results: list[GeoapifyPlace] = []
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    for f in data.get("features", []):
                        props = f.get("properties", {})
                        p_lat = props.get("lat")
                        p_lon = props.get("lon")
                        if p_lat is None or p_lon is None:
                            continue

                        name = props.get("name")
                        formatted_addr = props.get("formatted", "")
                        if not name:
                            # Generate descriptive name from address or street
                            street = props.get("street")
                            if "pharmacy" in category:
                                name = f"Nhà thuốc {street}" if street else f"Nhà thuốc ({formatted_addr[:30]}...)"
                            elif "fuel" in category:
                                name = f"Cây xăng {street}" if street else f"Cây xăng ({formatted_addr[:30]}...)"
                            elif "cafe" in category:
                                name = f"Quán Cà phê {street}" if street else f"Quán Cà phê ({formatted_addr[:30]}...)"
                            elif "restaurant" in category:
                                name = f"Quán Ăn {street}" if street else f"Quán Ăn ({formatted_addr[:30]}...)"
                            else:
                                name = f"Cơ sở Y tế {street}" if street else f"Cơ sở Y tế ({formatted_addr[:30]}...)"

                        contact = props.get("contact") or {}
                        phone = contact.get("phone")

                        # Extract opening hours if available
                        opening_hours = props.get("opening_hours")
                        if not opening_hours:
                            raw_ds = props.get("datasource", {}).get("raw", {})
                            opening_hours = raw_ds.get("opening_hours")

                        dist_m = float(props.get("distance", 0.0))
                        place_id = props.get("place_id") or f"geoapify-{len(results)+1}"
                        city = props.get("city") or "hcm"

                        results.append(
                            GeoapifyPlace(
                                id=place_id,
                                name=name,
                                category=category,
                                address=formatted_addr or name,
                                city=city,
                                lat=float(p_lat),
                                lon=float(p_lon),
                                distance_meters=dist_m,
                                phone=phone,
                                opening_hours=opening_hours,
                                datasource_raw=props.get("datasource", {}),
                            )
                        )
        except Exception as e:
            logger.warning(f"Geoapify places query failed: {e}")

        return results

    def calculate_routing(
        self,
        start_lat: float,
        start_lon: float,
        dest_lat: float,
        dest_lon: float,
        mode: str = "drive",
        avoid: str | None = None,
    ) -> GeoapifyRouteResult | None:
        """Calculate real-time turn-by-turn road route between waypoints."""
        geo_mode = (
            "motorcycle"
            if mode in ("motorcycle", "two_wheeler", "scooter")
            else ("walk" if mode in ("walk", "walking") else "drive")
        )
        avoid_param = f"&avoid={avoid}" if avoid else ""
        url = (
            f"https://api.geoapify.com/v1/routing"
            f"?waypoints={start_lat},{start_lon}|{dest_lat},{dest_lon}"
            f"&mode={geo_mode}"
            f"{avoid_param}"
            f"&details=instruction_details"
            f"&apiKey={self.api_key}"
        )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    features = data.get("features", [])
                    if not features:
                        return None

                    feature = features[0]
                    props = feature.get("properties", {})
                    dist_meters = float(props.get("distance", 0.0))
                    time_secs = float(props.get("time", 0.0))

                    # Parse legs and steps
                    steps: list[GeoapifyRouteStep] = []
                    legs = props.get("legs", [])
                    step_idx = 1
                    for leg in legs:
                        for s in leg.get("steps", []):
                            inst_obj = s.get("instruction", {})
                            inst_text = inst_obj.get("text", "")
                            s_dist = float(s.get("distance", 0.0))
                            s_time = float(s.get("time", 0.0))
                            road = inst_obj.get("road") or inst_obj.get("street")
                            if not road and inst_text:
                                m = re.search(r'\b(?:on|onto)\s+([^.]+)', inst_text, re.IGNORECASE)
                                if m:
                                    road = m.group(1).strip()
                                elif "destination" in inst_text.lower():
                                    road = "Điểm đến (Quầy thuốc GPP)"
                            if road and road.lower() in ("the left", "the right", "left", "right"):
                                road = "Điểm đến (Quầy thuốc GPP)"
                            vi_instruction = translate_step_instruction(inst_text, road)
                            steps.append(
                                GeoapifyRouteStep(
                                    step_number=step_idx,
                                    instruction=vi_instruction,
                                    distance_meters=s_dist,
                                    time_seconds=s_time,
                                    road_name=road,
                                )
                            )
                            step_idx += 1

                    # Parse polyline coordinates
                    geom = feature.get("geometry", {})
                    geom_type = geom.get("type")
                    raw_coords = geom.get("coordinates", [])

                    route_coords: list[tuple[float, float]] = []
                    if geom_type == "MultiLineString" and raw_coords:
                        for line in raw_coords:
                            for pt in line:
                                if len(pt) >= 2:
                                    route_coords.append((float(pt[1]), float(pt[0])))
                    elif geom_type == "LineString" and raw_coords:
                        for pt in raw_coords:
                            if len(pt) >= 2:
                                route_coords.append((float(pt[1]), float(pt[0])))

                    dist_km = round(dist_meters / 1000.0, 2)
                    eta_mins = max(1, int(round(time_secs / 60.0)))

                    return GeoapifyRouteResult(
                        distance_meters=dist_meters,
                        distance_km=dist_km,
                        duration_seconds=time_secs,
                        eta_minutes=eta_mins,
                        steps=steps,
                        coordinates=route_coords,
                    )
        except Exception as e:
            logger.warning(f"Geoapify routing API failed: {e}")

    def get_ip_info(self, ip: str = "") -> dict[str, Any]:
        """Lookup IP geolocation and sanitize to Vietnam boundaries."""
        url = f"https://api.geoapify.com/v1/ipinfo?apiKey={self.api_key}"
        if ip and ip not in ("127.0.0.1", "localhost", "::1", "testclient"):
            url += f"&ip={urllib.parse.quote(ip)}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    country_code = (data.get("country", {}).get("iso_code") or "").upper()
                    # If foreign IP (e.g., Tokyo, AWS US, etc.), do NOT blend foreign coordinates with Vietnam cities!
                    if country_code and country_code != "VN":
                        return {
                            "city": "hanoi",
                            "name": "Đang định vị vị trí thực của bạn",
                            "address": "Phố Bà La, Phường Đình Bảng, TP. Từ Sơn, Bắc Ninh",
                            "lat": 21.1078,
                            "lng": 105.9561,
                            "isForeignIpFallback": True,
                        }
                    city_name = data.get("city", {}).get("name") or "Đình Bảng, Từ Sơn"
                    loc = data.get("location", {})
                    lat = float(loc.get("latitude", 21.1078))
                    lng = float(loc.get("longitude", 105.9561))
                    city_id = "hanoi"
                    if lat < 14.5:
                        city_id = "hcm"
                    elif lat < 17.5:
                        city_id = "danang"
                    return {
                        "city": city_id,
                        "name": f"Vị trí mạng ({city_name})",
                        "address": city_name,
                        "lat": lat,
                        "lng": lng,
                        "isForeignIpFallback": False,
                    }
        except Exception as e:
            logger.warning(f"Geoapify ipinfo lookup failed: {e}")
        return {
            "city": "hanoi",
            "name": "Vị trí thực tế của bạn",
            "address": "Phố Bà La, Phường Đình Bảng, TP. Từ Sơn, Bắc Ninh",
            "lat": 21.1078,
            "lng": 105.9561,
            "isForeignIpFallback": True,
        }


# Global singleton client
geoapify_client = GeoapifyClient()
