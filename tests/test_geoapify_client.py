"""Unit tests for Geoapify Live Client integration."""

import pytest
from app.services.geoapify_client import GeoapifyClient, geoapify_client


def test_geoapify_client_initialization():
    """Verify that Geoapify client initializes with provided API key."""
    client = GeoapifyClient()
    assert client.api_key == "224447c8da3b4555a5380f31ddb56bf3"
    assert client.timeout > 0


def test_geoapify_geocode():
    """Verify real-time geocoding for Vietnamese urban location."""
    res = geoapify_client.geocode("Ben Thanh Ho Chi Minh")
    assert res is not None
    lat, lon, formatted = res
    assert 10.7 < lat < 10.8
    assert 106.6 < lon < 106.8
    assert "Vietnam" in formatted or "Thành phố Hồ Chí Minh" in formatted or "Ben Thanh" in formatted or "Bến Thành" in formatted


def test_geoapify_search_nearby_pharmacies():
    """Verify live search for nearby pharmacies using Geoapify Places API."""
    # Coordinates in District 1, HCM
    lat, lon = 10.7720, 106.6983
    places = geoapify_client.search_nearby_places(lat=lat, lon=lon, category="healthcare.pharmacy", radius_meters=3000, limit=5)
    assert len(places) > 0
    first = places[0]
    assert first.lat > 0
    assert first.lon > 0
    assert first.address
    assert first.distance_meters >= 0


def test_geoapify_search_nearby_hospitals():
    """Verify live search for nearby emergency hospitals using Geoapify Places API."""
    lat, lon = 10.7720, 106.6983
    hospitals = geoapify_client.search_nearby_places(lat=lat, lon=lon, category="healthcare.hospital", radius_meters=5000, limit=5)
    assert len(hospitals) > 0
    assert any("bệnh viện" in h.name.lower() or "hospital" in h.name.lower() or "cơ sở y tế" in h.name.lower() for h in hospitals)


def test_geoapify_realtime_routing():
    """Verify real-time road routing, turn-by-turn steps and polyline geometry from Geoapify."""
    # From District 1 to Chợ Rẫy Hospital
    start_lat, start_lon = 10.7720, 106.6983
    dest_lat, dest_lon = 10.7578, 106.6596

    route = geoapify_client.calculate_routing(start_lat, start_lon, dest_lat, dest_lon, mode="drive")
    assert route is not None
    assert route.distance_km > 3.0
    assert route.eta_minutes > 0
    assert len(route.steps) >= 3
    assert len(route.coordinates) > 10
    # Step instructions should be populated
    assert any(s.instruction for s in route.steps)
