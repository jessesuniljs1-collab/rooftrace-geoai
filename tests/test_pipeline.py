import base64
import io
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import app
from rooftrace import inference as engine

client = TestClient(app)


def image_bytes(size=(512, 512), fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", size).save(buffer, fmt)
    return buffer.getvalue()


def test_validation_and_bounds():
    for data in [b"not an image", image_bytes(fmt="GIF"), image_bytes((2049, 64)), image_bytes((63, 100)), b"x" * 3_500_001]:
        with pytest.raises(ValueError):
            engine.decode_image(data)
    assert engine.decode_image(image_bytes((1231, 613), "JPEG")).size == (1231, 613)


def test_exif_orientation():
    buffer = io.BytesIO()
    image = Image.new("RGB", (100, 200))
    exif = image.getexif()
    exif[274] = 6
    image.save(buffer, "JPEG", exif=exif)
    assert engine.decode_image(buffer.getvalue()).size == (200, 100)


def test_regions_thresholds_coordinates_and_zero():
    probability = np.zeros((64, 100), dtype=np.uint8)
    probability[10:20, 30:50] = 200
    probability[40:50, 80:100] = 120
    regions = engine.regions_from_probability(probability, 0.5)
    assert len(regions) == 1
    assert [regions[0][key] for key in ["x_min", "y_min", "x_max", "y_max", "area_pixels"]] == [30, 10, 50, 20, 200]
    assert len(engine.regions_from_probability(probability, 0.4)) == 2
    assert engine.regions_from_probability(probability, 0.9) == []
    assert engine.regions_from_probability(np.zeros((64, 64), np.uint8), 0.5) == []
    assert np.array_equal(engine.decode_probability(engine.encode_probability(probability)), probability)


def test_tiling_stitch_alignment_and_duplicate_merging(monkeypatch):
    class PixelModel:
        def run(self, _, inputs):
            value = inputs["rgb"][:, 0] * 20 - 10
            return [np.stack([-value, value], axis=1)]
    monkeypatch.setattr(engine, "get_session", lambda: PixelModel())
    pixels = np.zeros((721, 907, 3), dtype=np.uint8)
    pixels[200:650, 300:800] = 255
    probability, timing = engine.predict(Image.fromarray(pixels))
    result = engine.regions_from_probability(probability, 0.5)
    assert probability.shape == (721, 907)
    assert timing["tiles"] == 6
    assert len(result) == 1  # Region crosses overlapping tiles, counted once.
    assert [result[0][key] for key in ["x_min", "y_min", "x_max", "y_max"]] == [300, 200, 800, 650]
    small, _ = engine.predict(Image.new("RGB", (64, 93)))
    assert small.shape == (93, 64)


def test_api_rejects_invalid_inputs():
    assert client.post("/api/analyze").status_code == 422
    assert client.post("/api/analyze", data={"sample_id": "../secret"}).status_code == 404
    assert client.post("/api/analyze", files={"file": ("bad.png", b"corrupt", "image/png")}).status_code == 422
    assert client.post("/api/analyze", files={"file": ("huge.png", image_bytes((2049, 64)), "image/png")}).status_code == 422
    assert client.post("/api/analyze", content=b"a" * 3_600_000).status_code == 413
    assert client.post("/api/regions", json={"probability_png": "bad", "threshold": .5}).status_code == 422
    assert client.post("/api/regions", json={"probability_png": base64.b64encode(image_bytes()).decode(), "threshold": .99}).status_code == 422


def test_real_sample_upload_filter_and_zero():
    sample = client.post("/api/analyze", data={"sample_id": "courtyard", "threshold": .5})
    assert sample.status_code == 200, sample.text
    result = sample.json()
    assert result["count"] == len(result["regions"]) and result["count"] > 0
    image = (engine.ROOT / "static/samples/courtyard.png").read_bytes()
    uploaded = client.post("/api/analyze", files={"file": ("test.png", image, "image/png")}).json()
    assert uploaded["regions"] == result["regions"]
    assert uploaded["image_id"] != result["image_id"]
    for threshold in [.1, .5, .9]:
        response = client.post("/api/regions", json={"probability_png": result["probability_png"], "threshold": threshold})
        assert response.status_code == 200
        assert response.json()["regions"] == engine.regions_from_probability(engine.decode_probability(result["probability_png"]), threshold)
    zero = client.post("/api/analyze", files={"file": ("blank.png", image_bytes(), "image/png")})
    assert zero.status_code == 200
    assert zero.json()["count"] == 0
    assert zero.headers["cache-control"] == "no-store"


def test_concurrent_filter_requests_stay_isolated():
    def run(index):
        probability = np.zeros((64, 64), dtype=np.uint8)
        probability[10:20, index:index + 5] = 255
        response = client.post("/api/regions", json={"probability_png": engine.encode_probability(probability), "threshold": .5})
        return response.json()["regions"][0]["x_min"]
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert list(pool.map(run, [5, 25, 45])) == [5, 25, 45]


def test_static_entry_and_health():
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert len(client.get("/api/samples").json()) >= 3
    assert client.get("/health").json()["status"] == "ok"
