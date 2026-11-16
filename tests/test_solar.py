import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import app
from rooftrace import solar
from rooftrace.inference import encode_probability
from rooftrace.sunroof_geometry import meters_per_pixel, rotate_points

client = TestClient(app)
WEATHER = dict(annual_kwh_per_kwp=1500, monthly_kwh_per_kwp=[125] * 12, provider="test fixture only")


def test_upstream_geometry_scale_and_rotation():
    assert meters_per_pixel(0, 0) == pytest.approx(156543.033928)
    assert meters_per_pixel(60, 19) == pytest.approx(meters_per_pixel(0, 19) / 2)
    assert meters_per_pixel(13, 19, 2) == pytest.approx(meters_per_pixel(13, 19) / 2)
    assert np.allclose(rotate_points([[1, 0]], 90), [[0, 1]])
    with pytest.raises(ValueError):
        meters_per_pixel(90, 20)


def test_physical_scale_area_panels_and_energy():
    probability = np.zeros((100, 100), dtype=np.uint8)
    probability[10:90, 10:90] = 255
    settings = solar.SolarSettings(meters_per_pixel=.25, latitude=13, longitude=77,
                                  usable_fraction=.6, additional_shade_percent=10)
    result = solar.analyze_solar(probability, .5, settings, weather=WEATHER)
    roof = result["roofs"][0]
    assert roof["footprint_m2"] == 400
    assert 0 < roof["panel_count"] <= int(400 * .6 / 2.2)
    assert roof["capacity_kwp"] == pytest.approx(roof["panel_count"] * .45)
    assert roof["annual_kwh"] == pytest.approx(round(roof["capacity_kwp"] * 1500 * .9, 1))
    assert len(roof["monthly_kwh"]) == 12
    # All actual rasterized panel footprints stay within the roof; a hole is respected.
    for corners in roof["panels"]:
        patch = np.zeros_like(probability)
        cv2.fillConvexPoly(patch, np.rint(corners).astype(np.int32), 1)
        assert not np.any((patch > 0) & (probability == 0))
    excluded = solar.analyze_solar(probability, .5, settings.model_copy(update={"excluded_region_ids": [1]}), weather=WEATHER)
    assert excluded["panel_count"] == excluded["annual_kwh"] == 0


def test_holes_and_setback_are_not_filled_with_panels():
    probability = np.zeros((100, 100), dtype=np.uint8)
    probability[5:95, 5:95] = 255
    probability[30:70, 30:70] = 0
    result = solar.analyze_solar(probability, .5, solar.SolarSettings(meters_per_pixel=.25, latitude=13, longitude=77), weather=WEATHER)
    for roof in result["roofs"]:
        for corners in roof["panels"]:
            patch = np.zeros_like(probability)
            cv2.fillConvexPoly(patch, np.rint(corners).astype(np.int32), 1)
            assert not np.any((patch > 0) & (probability == 0))


def test_empty_result_does_not_call_weather(monkeypatch):
    def fail(_):
        raise AssertionError("Should not fetch climate data for zero capacity")
    monkeypatch.setattr(solar, "get_pvgis", fail)
    result = solar.analyze_solar(np.zeros((64, 64), np.uint8), .5, solar.SolarSettings(meters_per_pixel=.3, latitude=13, longitude=77))
    assert result["roofs"] == [] and result["annual_kwh"] == 0 and result["weather"] is None


def test_solar_api_and_invalid_inputs(monkeypatch):
    monkeypatch.setattr(solar, "get_pvgis", lambda _: WEATHER)
    probability = np.zeros((64, 64), np.uint8)
    probability[5:55, 5:55] = 255
    body = dict(probability_png=encode_probability(probability), threshold=.5,
                settings=dict(meters_per_pixel=.3, latitude=13, longitude=77))
    result = client.post("/api/solar", json=body)
    assert result.status_code == 200
    assert result.json()["capacity_kwp"] > 0
    body["settings"]["meters_per_pixel"] = 0
    assert client.post("/api/solar", json=body).status_code == 422


def test_weather_failure_is_honest(monkeypatch):
    def fail(_):
        raise RuntimeError("PVGIS unavailable; no estimate")
    monkeypatch.setattr(solar, "get_pvgis", fail)
    probability = np.zeros((64, 64), np.uint8)
    probability[5:55, 5:55] = 255
    response = client.post("/api/solar", json=dict(probability_png=encode_probability(probability), threshold=.5,
        settings=dict(meters_per_pixel=.3, latitude=13, longitude=77)))
    assert response.status_code == 503 and "no estimate" in response.json()["detail"]
