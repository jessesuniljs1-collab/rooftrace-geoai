"""Real HTTP smoke test of solar scenarios. Does not substitute cached predictions."""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    session = requests.Session()
    session.trust_env = False
    home = session.get(base, timeout=60)
    assert home.status_code == 200 and "RoofTrace Solar" in home.text
    response = session.post(base + "/api/analyze", data={"sample_id": "uttari"}, timeout=120)
    response.raise_for_status()
    detection = response.json()
    settings = dict(meters_per_pixel=.2, latitude=12.821725, longitude=77.488795)
    body = dict(probability_png=detection["probability_png"], threshold=.5, settings=settings)
    started = time.perf_counter()
    response = session.post(base + "/api/solar", json=body, timeout=120)
    response.raise_for_status()
    result = response.json()
    latency = round(time.perf_counter() - started, 3)
    assert result["roof_count"] == detection["count"] and result["panel_count"] > 0
    assert result["capacity_kwp"] == round(result["panel_count"] * .45, 3)
    assert result["annual_kwh"] > 0 and len(result["monthly_kwh"]) == 12
    assert result["weather"]["source"] == "live PVGIS API calculation"
    for roof in result["roofs"]:
        assert roof["footprint_m2"] == round(roof["area_pixels"] * .04, 2)
        assert len(roof["panels"]) == roof["panel_count"]
        for panel in roof["panels"]:
            assert all(0 <= x < detection["width"] and 0 <= y < detection["height"] for x, y in panel)
    body["settings"]["excluded_region_ids"] = [result["roofs"][0]["id"]]
    excluded = session.post(base + "/api/solar", json=body, timeout=120)
    excluded.raise_for_status()
    assert excluded.json()["panel_count"] < result["panel_count"]
    body["settings"]["excluded_region_ids"] = []
    body["threshold"] = .7
    filtered = session.post(base + "/api/solar", json=body, timeout=120)
    filtered.raise_for_status()
    assert filtered.json()["threshold"] == .7
    report = dict(verified_at_ist=datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(), base_url=base,
                  no_authentication_sent=True, checks=["real India inference", "live PVGIS solar calculation", "mask-area conversion", "panel coordinates bounded", "capacity arithmetic", "12 monthly outputs", "region exclusion", "threshold recomputation"],
                  measured_solar_request_seconds=latency,
                  scenario={k: v for k, v in result.items() if k != "roofs"},
                  per_roof=[{k: v for k, v in roof.items() if k != "panels"} for roof in result["roofs"]],
                  scope="Reproducibility smoke test of a scenario; no measured solar-production ground truth or guaranteed installation suitability.")
    output = ROOT / ("docs/solar-public-verification.json" if base.startswith("https") else "docs/solar-local-verification.json")
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"base_url":base,"checks":report["checks"],"roof_regions":result["roof_count"],"panels":result["panel_count"],"kwp":result["capacity_kwp"],"annual_kwh":result["annual_kwh"],"elapsed_seconds":latency}, indent=2))


if __name__ == "__main__":
    main()
