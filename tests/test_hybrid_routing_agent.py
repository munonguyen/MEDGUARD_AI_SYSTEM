"""Unit and Integration Tests for Hybrid POI Hub & Cost-Free Traffic Routing Agent."""

from datetime import datetime
import zoneinfo
import pytest

from app.models.chat import ChatMessage, ChatRequest, ChatContext
from app.core.context import RequestContext
from app.services.chat import orchestrate_chat
from app.services.hybrid_poi_hub import (
    HybridPoiHub,
    evaluate_operating_hours,
    hub_instance,
)
from app.services.traffic_routing_agent import (
    TrafficRoutingAgent,
    _calculate_haversine_km,
    geo_routing_agent,
)


def test_haversine_distance_calculation():
    """Verify distance accuracy between known coordinates (Chợ Rẫy to Bệnh viện 115)."""
    # BV Chợ Rẫy: 10.7578, 106.6596
    # BV 115: 10.7756, 106.6667
    dist = _calculate_haversine_km(10.7578, 106.6596, 10.7756, 106.6667)
    assert 2.0 <= dist <= 2.3


def test_operating_hours_evaluation():
    """Verify 24/7 status, open status, closing soon, and closed states."""
    # 1. 24/7 Facility
    op_247 = evaluate_operating_hours({"is_24_7": True, "open": "00:00", "close": "23:59"})
    assert op_247.is_open is True
    assert op_247.status_badge == "OPEN_24_7"
    assert "24/7" in op_247.status_label

    # 2. Daytime open (e.g. at 14:00 for 06:30 - 22:30 store)
    dt_day = datetime(2026, 10, 17, 14, 0)
    op_day = evaluate_operating_hours({"is_24_7": False, "open": "06:30", "close": "22:30"}, check_time=dt_day)
    assert op_day.is_open is True
    assert op_day.status_badge == "OPEN_NOW"
    assert op_day.minutes_until_close == 8 * 60 + 30

    # 3. Closing soon (< 30 minutes, e.g. at 22:15 for 22:30 closing)
    dt_closing_soon = datetime(2026, 10, 17, 22, 15)
    op_closing_soon = evaluate_operating_hours({"is_24_7": False, "open": "06:30", "close": "22:30"}, check_time=dt_closing_soon)
    assert op_closing_soon.is_open is True
    assert op_closing_soon.status_badge == "CLOSING_SOON"
    assert op_closing_soon.minutes_until_close == 15

    # 4. Closed (e.g. at 23:15 for 22:30 closing)
    dt_closed = datetime(2026, 10, 17, 23, 15)
    op_closed = evaluate_operating_hours({"is_24_7": False, "open": "06:30", "close": "22:30"}, check_time=dt_closed)
    assert op_closed.is_open is False
    assert op_closed.status_badge == "CLOSED"
    assert "ĐÃ ĐÓNG CỬA" in op_closed.status_label


def test_hybrid_hub_listing_and_filtering():
    """Verify that hub correctly returns emergency facilities and pharmacies."""
    hcm_emergencies = hub_instance.list_pois(poi_type="emergency", city="hcm")
    assert len(hcm_emergencies) >= 3
    assert any("Chợ Rẫy" in p.name for p in hcm_emergencies)

    hcm_pharmacies = hub_instance.list_pois(poi_type="pharmacy", city="hcm")
    assert len(hcm_pharmacies) >= 3
    assert any("Long Châu" in p.name for p in hcm_pharmacies)
    assert any("Pharmacity" in p.name for p in hcm_pharmacies)

    hanoi_emergencies = hub_instance.list_pois(poi_type="emergency", city="hanoi")
    assert any("Bạch Mai" in p.name for p in hanoi_emergencies)


def test_traffic_routing_agent_rush_hour_optimization():
    """Verify that routing agent models rush hour congestion and recommends bypass route."""
    # Simulate evening rush hour: 17:45 in HCM
    dt_rush = datetime(2026, 10, 17, 17, 45)
    plan = geo_routing_agent.plan_destination_routing(
        query="Bệnh nhân đột quỵ méo miệng cần xe cấp cứu gấp",
        location_hint="Quận 1, TP.HCM",
        forced_poi_type="emergency",
        check_time=dt_rush,
    )

    assert plan.query_type == "emergency"
    assert plan.is_rush_hour is True
    assert plan.selected_poi.poi_type == "hospital_emergency"
    # Alternative bypass route should be computed
    assert plan.alternative_route is not None
    assert plan.recommended_route_type == "OPTIMAL_BYPASS"
    assert plan.alternative_route.time_saved_minutes >= 3
    assert "https://www.google.com/maps/dir/?api=1" in plan.google_maps_turn_by_turn_url
    assert "driving" in plan.google_maps_turn_by_turn_url


def test_traffic_routing_agent_off_peak():
    """Verify that routing agent selects primary direct route during off-peak."""
    # Simulate night time: 22:00
    dt_off_peak = datetime(2026, 10, 17, 22, 0)
    plan = geo_routing_agent.plan_destination_routing(
        query="Tôi muốn tìm quầy thuốc gần nhất",
        location_hint="Quận 3, TP.HCM",
        forced_poi_type="pharmacy",
        check_time=dt_off_peak,
    )

    assert plan.query_type == "pharmacy"
    assert plan.is_rush_hour is False
    assert plan.recommended_route_type == "PRIMARY_DIRECT"
    assert plan.selected_poi.poi_type == "pharmacy"
    assert plan.selected_poi.operating_status.is_open is True


def test_orchestrate_chat_pipeline_pharmacy_location_intent():
    """End-to-end integration test: User asks for pharmacy location and gets geo_routing."""
    ctx = RequestContext(request_id="test-geo-pharmacy-1", tenant_id="tenant-1", idempotency_key="key-geo-1")
    payload = ChatRequest(
        conversation_id="conv-geo-pharm-1",
        messages=[
            ChatMessage(
                role="user",
                content="Tôi đang bị cảm nhẹ ở Quận 1, cho tôi hỏi hiệu thuốc gần nhất ở đâu và bản đồ chỉ đường?",
            )
        ],
        context=ChatContext(patient_ref="Quận 1, TP.HCM"),
    )

    response = orchestrate_chat(payload, ctx)
    assert response.status == "answered"
    assert response.answer is not None
    assert response.answer.geo_routing is not None
    geo = response.answer.geo_routing
    assert geo["query_type"] == "pharmacy"
    assert geo["selected_poi"]["name"]
    assert geo["selected_poi"]["operating_status"]["is_open"] is True
    assert "google_maps_turn_by_turn_url" in geo
    assert len(geo["primary_route"]["steps"]) > 0


def test_orchestrate_chat_pipeline_emergency_location_intent():
    """End-to-end integration test: User in critical emergency gets both transit and geo_routing."""
    ctx = RequestContext(request_id="test-geo-emergency-1", tenant_id="tenant-1", idempotency_key="key-geo-2")
    payload = ChatRequest(
        conversation_id="conv-geo-emerg-1",
        messages=[
            ChatMessage(
                role="user",
                content="Bố tôi 68 tuổi bỗng dưng ngã quỵ, méo miệng và ú ớ không nói được, chỗ cấp cứu gần nhất ở đâu?",
            )
        ],
        context=ChatContext(age=68, patient_ref="Quận 10, TP.HCM"),
    )

    response = orchestrate_chat(payload, ctx)
    assert response.status == "answered"
    assert response.answer is not None
    assert response.answer.emergency_transit is not None
    assert response.answer.geo_routing is not None
    geo = response.answer.geo_routing
    assert geo["query_type"] == "emergency"
    assert "Chợ Rẫy" in geo["selected_poi"]["name"] or "115" in geo["selected_poi"]["name"]
    assert geo["selected_poi"]["operating_status"]["status_badge"] == "OPEN_24_7"
