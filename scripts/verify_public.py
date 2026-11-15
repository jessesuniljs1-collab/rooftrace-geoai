"""Exercise public HTTP entry points without credentials or cookies."""
import io
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "https://rooftrace-geoai.vercel.app"
    session = requests.Session()
    session.trust_env = False
    checks = []

    def record(name, response, expected=200):
        assert response.status_code == expected, (name, response.status_code, response.text[:300])
        checks.append(dict(check=name, status=response.status_code))
        return response

    home = record("public home, no login", session.get(base, timeout=120))
    assert home.url.rstrip("/") == base.rstrip("/") and "RoofTrace" in home.text
    health = record("health", session.get(base + "/health", timeout=120)).json()
    manifest = record("samples", session.get(base + "/api/samples", timeout=60)).json()
    results = {}
    for sample in manifest:
        started = time.perf_counter()
        result = record("inference: " + sample["id"], session.post(base + "/api/analyze", data={"sample_id": sample["id"], "threshold": .5}, timeout=180)).json()
        assert result["count"] == len(result["regions"])
        for r in result["regions"]:
            assert 0 <= r["x_min"] < r["x_max"] <= result["width"]
            assert 0 <= r["y_min"] < r["y_max"] <= result["height"]
        results[sample["id"]] = dict(count=result["count"], model_seconds=result["inference_seconds"], wall_seconds=round(time.perf_counter() - started, 3))
        if sample["id"] == "courtyard":
            reference = result
    image = (ROOT / "static/samples/courtyard.png").read_bytes()
    uploaded = record("uploaded PNG inference", session.post(base + "/api/analyze", files={"file": ("courtyard.png", image, "image/png")}, timeout=180)).json()
    assert uploaded["regions"] == reference["regions"] and uploaded["image_id"] != reference["image_id"]
    filtered = record("threshold filtering", session.post(base + "/api/regions", json={"probability_png": reference["probability_png"], "threshold": .7}, timeout=60)).json()
    assert filtered["count"] == len(filtered["regions"]) and filtered["threshold"] == .7
    buffer = io.BytesIO()
    Image.new("RGB", (512, 512)).save(buffer, "JPEG")
    blank = record("uploaded JPG zero regions", session.post(base + "/api/analyze", files={"file": ("blank.jpg", buffer.getvalue(), "image/jpeg")}, timeout=180)).json()
    assert blank["count"] == 0
    record("corrupt image rejected", session.post(base + "/api/analyze", files={"file": ("bad.png", b"invalid", "image/png")}, timeout=60), 422)
    record("oversized upload rejected", session.post(base + "/api/analyze", files={"file": ("large.png", b"x" * 3_600_000, "image/png")}, timeout=60), 413)
    repository = record("public repository API", session.get("https://api.github.com/repos/jessesuniljs1-collab/rooftrace-geoai", timeout=60)).json()
    assert repository["private"] is False
    report = dict(verified_at_ist=datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
                  base_url=base, no_authentication_sent=True, health=health, checks=checks,
                  sample_results=results, filtered_threshold=.7, filtered_count=filtered["count"],
                  public_repository=repository["html_url"], repository_private=repository["private"])
    (ROOT / "docs/public-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
