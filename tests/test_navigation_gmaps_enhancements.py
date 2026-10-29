"""Unit tests for Google Maps navigation enhancements: vehicle mode, avoidances, amenities along route."""

from fastapi.testclient import TestClient
import pytest
from app.main import app

client = TestClient(app)

def test_geo_route_with_motorcycle_and_avoidances():
    payload = {
        "start_lat": 10.7578,
        "start_lng": 106.6596,
        "dest_lat": 10.7756,
        "dest_lng": 106.6667,
        "mode": "motorcycle",
        "avoid_highways": True,
        "avoid_tolls": True,
    }
    response = client.post("/v1/geo/route", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "distance_km" in data
    assert "eta_minutes" in data
    assert "steps" in data
    assert data["mode"] == "motorcycle"
    assert "travelmode=two_wheeler" in data["google_maps_turn_by_turn_url"]
    assert "dir_action=navigate" in data["google_maps_turn_by_turn_url"]
    assert "avoid=t,h" in data["google_maps_turn_by_turn_url"] or "avoid=h" in data["google_maps_turn_by_turn_url"]

def test_geo_pois_along_route_gas_station():
    response = client.get("/v1/geo/pois?poi_type=gas_station&lat=10.7578&lng=106.6596")
    assert response.status_code == 200
    data = response.json()
    assert data["poi_type"] == "gas_station"
    assert "pois" in data
    assert isinstance(data["pois"], list)
    if data["pois"]:
        first = data["pois"][0]
        assert "distance_km" in first
        assert "operating_status" in first
        assert "travelmode=two_wheeler" in first["google_maps_turn_by_turn_url"]
