"""Aligned, overlap-averaged building segmentation in original image pixels."""
import base64
import hashlib
import io
import json
import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "whu-unetplusplus-efficientnet-b4-09df9efd-onnx17"
MAX_BYTES = 3_500_000
MAX_PIXELS = 4_194_304
MAX_SIDE = 2048
MIN_AREA = 16
TILE = 512
STRIDE = 384
_session = None
_load_lock = threading.Lock()
INFERENCE_GATE = threading.BoundedSemaphore(1)
cv2.setNumThreads(1)


def decode_image(data: bytes) -> Image.Image:
    if len(data) > MAX_BYTES:
        raise ValueError("Image exceeds the 3.5 MB upload limit.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG"}:
                raise ValueError("Please use a JPG or PNG image.")
            width, height = image.size
            if min(width, height) < 64 or max(width, height) > MAX_SIDE or width * height > MAX_PIXELS:
                raise ValueError("Use an image between 64 and 2048 pixels on each side. Please resize larger images before uploading.")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("Animated or multi-frame images are not supported.")
            image.load()
            image = ImageOps.exif_transpose(image)
            if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGBA", rgba.size, "white")
                image = Image.alpha_composite(background, rgba)
            return image.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("This file could not be decoded as a valid JPG or PNG image.") from error


def get_session():
    global _session
    with _load_lock:
        if _session is None:
            path = Path(os.environ.get("ROOFTRACE_MODEL_PATH", ROOT / "models" / "rooftrace-whu.onnx"))
            manifest = json.loads((ROOT / "models" / "manifest.json").read_text())
            if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["onnx_sha256"]:
                raise RuntimeError("Model checksum mismatch. Run scripts/download_model.py.")
            options = ort.SessionOptions()
            options.intra_op_num_threads = int(os.environ.get("ROOFTRACE_THREADS", "2"))
            options.inter_op_num_threads = 1
            options.enable_cpu_mem_arena = False
            _session = ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
    return _session


def tile_starts(length: int):
    if length <= TILE:
        return [0]
    return sorted(set([*range(0, length - TILE + 1, STRIDE), length - TILE]))


def predict(image: Image.Image):
    """No spatial resizing. Pad edge tiles, average overlap, then quantize once."""
    started = time.perf_counter()
    session = get_session()
    array = np.asarray(image, dtype=np.float32) / 255.0
    height, width = array.shape[:2]
    total = np.zeros((height, width), dtype=np.float32)
    weights = np.zeros_like(total)
    tiles = 0
    for y in tile_starts(height):
        for x in tile_starts(width):
            crop = array[y:y + TILE, x:x + TILE]
            h, w = crop.shape[:2]
            padded = np.pad(crop, ((0, TILE - h), (0, TILE - w), (0, 0)), mode="reflect")
            tensor = np.ascontiguousarray(padded.transpose(2, 0, 1)[None])
            logits = session.run(None, {"rgb": tensor})[0][0]
            # Stable two-class softmax, returned as the building probability.
            delta = np.clip(logits[0] - logits[1], -80, 80)
            probability = 1.0 / (1.0 + np.exp(delta))
            total[y:y + h, x:x + w] += probability[:h, :w]
            weights[y:y + h, x:x + w] += 1
            tiles += 1
    result = np.rint(total / weights * 255).astype(np.uint8)
    return result, {"inference_seconds": round(time.perf_counter() - started, 3), "tiles": tiles}


def encode_probability(probability: np.ndarray) -> str:
    buffer = io.BytesIO()
    Image.fromarray(probability).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def decode_probability(value: str) -> np.ndarray:
    try:
        raw = base64.b64decode(value, validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            w, h = image.size
            if image.format != "PNG" or image.mode != "L" or min(w, h) < 64 or max(w, h) > MAX_SIDE or w * h > MAX_PIXELS:
                raise ValueError("Invalid probability map dimensions or format.")
            image.load()
            return np.array(image, dtype=np.uint8)
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise ValueError("Invalid probability map. Analyze the image again.") from error


def regions_from_probability(probability: np.ndarray, threshold: float):
    if not np.isfinite(threshold) or not 0.1 <= threshold <= 0.9:
        raise ValueError("Probability threshold must be between 0.10 and 0.90.")
    mask = (probability.astype(np.float32) / 255 >= threshold).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    sums = np.bincount(labels.ravel(), weights=probability.ravel(), minlength=count)
    regions = []
    for label in range(1, count):
        x, y, width, height, area = (int(v) for v in stats[label])
        if area < MIN_AREA:
            continue
        regions.append(dict(id=len(regions) + 1, class_name="building_region", x_min=x, y_min=y,
                            x_max=x + width, y_max=y + height, area_pixels=area,
                            mean_probability=round(float(sums[label] / area / 255), 4)))
        if len(regions) > 5000:
            raise ValueError("Too many regions to display safely. Try a smaller crop or higher threshold.")
    return regions
