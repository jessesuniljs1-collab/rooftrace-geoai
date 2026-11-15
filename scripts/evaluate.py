"""Small diagnostic, not a benchmark. Fixed threshold; no test-set fitting."""
import json
import platform
import statistics
import sys
from pathlib import Path

import cv2
import numpy as np
import requests
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rooftrace.inference import MIN_AREA, ROOT, predict, regions_from_probability

REVISION = "c9ccc03ef4dd004b63cf179835771ab5e074bd3d"


def kept_labels(mask):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, np.int32)
    next_id = 1
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= MIN_AREA:
            keep[i] = next_id
            next_id += 1
    return keep[labels], next_id - 1


def score_regions(prediction, truth):
    pred, pn = kept_labels(prediction)
    true, tn = kept_labels(truth)
    intersections = np.bincount((pred * (tn + 1) + true).ravel(), minlength=(pn + 1) * (tn + 1)).reshape(pn + 1, tn + 1)
    pa = np.bincount(pred.ravel(), minlength=pn + 1)
    ta = np.bincount(true.ravel(), minlength=tn + 1)
    unions = pa[:, None] + ta[None, :] - intersections
    ious = intersections / np.maximum(unions, 1)
    candidates = [(float(ious[i, j]), i, j) for i in range(1, pn + 1)
                  for j in range(1, tn + 1) if ious[i, j] >= 0.5]
    seen_p, seen_t = set(), set()
    for _, i, j in sorted(candidates, reverse=True):
        if i not in seen_p and j not in seen_t:
            seen_p.add(i)
            seen_t.add(j)
    return len(seen_p), pn - len(seen_p), tn - len(seen_t), pn, tn


def main():
    folder = ROOT / "private" / "eval"
    folder.mkdir(parents=True, exist_ok=True)
    smoke = []
    for path in sorted((ROOT / "static" / "samples").glob("*.png")):
        image = Image.open(path).convert("RGB")
        probability, timing = predict(image)
        regions = regions_from_probability(probability, 0.5)
        draw = ImageDraw.Draw(image)
        for r in regions:
            draw.rectangle((r["x_min"], r["y_min"], r["x_max"] - 1, r["y_max"] - 1), outline="#74ff9c", width=2)
        image.save(folder / f"{path.stem}-smoke.png")
        smoke.append(dict(image=path.name, count=len(regions), **timing))
    rows = []
    totals = np.zeros(5, np.int64)
    pixels = np.zeros(3, np.int64)
    for number in range(1, 7):
        name = f"test_{number:04d}.png"
        for kind in ("Image", "Mask"):
            path = folder / f"{kind}-{name}"
            if not path.exists():
                url = f"https://huggingface.co/datasets/giswqs/WHU-Building-Dataset/resolve/{REVISION}/test/{kind}/{name}"
                response = requests.get(url, timeout=120)
                response.raise_for_status()
                path.write_bytes(response.content)
        image = Image.open(folder / f"Image-{name}").convert("RGB")
        truth = np.asarray(Image.open(folder / f"Mask-{name}").convert("L")) > 0
        probability, timing = predict(image)
        prediction = probability.astype(np.float32) / 255 >= 0.5
        counts = score_regions(prediction, truth)
        totals += counts
        pixels += [np.sum(prediction & truth), np.sum(prediction & ~truth), np.sum(~prediction & truth)]
        rows.append(dict(image=name, true_positive=counts[0], false_positive=counts[1], false_negative=counts[2],
                         predicted_regions=counts[3], reference_regions=counts[4], **timing))
    tp, fp, fn, pn, tn = map(int, totals)
    report = dict(dataset="giswqs/WHU-Building-Dataset", revision=REVISION, split="test",
                  selection="First six lexicographic test tiles, chosen before inference; no threshold fitting",
                  probability_threshold=0.5, min_component_area_pixels=MIN_AREA,
                  matching="8-connected regions from both masks, greedy one-to-one mask IoU >= 0.50",
                  precision=tp / max(tp + fp, 1), recall=tp / max(tp + fn, 1),
                  mean_absolute_count_error=statistics.mean(abs(r["predicted_regions"] - r["reference_regions"]) for r in rows),
                  pixel_precision=float(pixels[0] / max(pixels[0] + pixels[1], 1)),
                  pixel_recall=float(pixels[0] / max(pixels[0] + pixels[2], 1)),
                  median_warm_inference_seconds=statistics.median(r["inference_seconds"] for r in rows),
                  hardware=dict(system=platform.platform(), processor=platform.processor(), runtime="ONNX Runtime 1.20.1 CPU, 2 threads"),
                  caution="Six related tiles only, not a geographically broad benchmark. Provider-declared test split; independence not independently audited. Counts refer to connected regions, including reference labels, not cadastral instances. USGS samples are a separate geography and resolution without reference labels.",
                  true_positive=tp, false_positive=fp, false_negative=fn, rows=rows, public_sample_smoke=smoke)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
