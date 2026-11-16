"""Prepare the WorldStrat Bengaluru sample; prep-only rasterio and remotezip.

HTTP range reads retrieve one TIFF, not the 40 GB archive. No AI upscaling.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from remotezip import RemoteZip

ROOT = Path(__file__).resolve().parents[1]
REVISION = "704a57c6e4910918212723dca35f80cd03735792"
ARCHIVE = f"https://huggingface.co/datasets/Khlaifiabilel/worldstrat-agrisr/resolve/{REVISION}/hr_dataset.zip"
MEMBER = "hr_dataset/Landcover-769378/Landcover-769378_ps.tiff"
BOUNDS = [77.74346156428307, 13.004958175512426, 77.75803702681104, 13.01925023382535]
CROP = [450, 750, 750, 1050]  # left, top, right, bottom in original 1054px tile


def main():
    folder = ROOT / "private/worldstrat"
    folder.mkdir(parents=True, exist_ok=True)
    original = folder / Path(MEMBER).name
    if not original.exists():
        with RemoteZip(ARCHIVE, initial_buffer_size=1_048_576) as archive:
            original.write_bytes(archive.read(MEMBER))
    with rasterio.open(original) as source:
        rgb = source.read([1, 2, 3]).transpose(1, 2, 0)
    # 0.5 m output sampling does not create 0.5 m native detail.
    low, high = np.percentile(rgb, [1, 99], axis=(0, 1))
    rgb = np.clip((rgb - low) / np.maximum(high - low, 1) * 255, 0, 255).astype(np.uint8)
    image = Image.fromarray(rgb).crop(CROP).resize((900, 900), Image.Resampling.BILINEAR)
    target = ROOT / "static/samples/bengaluru.png"
    image.save(target)
    left, bottom, right, top = BOUNDS
    x0, y0, x1, y1 = CROP
    crop_bounds = [left + x0 / 1054 * (right - left), top - y1 / 1054 * (top - bottom),
                   left + x1 / 1054 * (right - left), top - y0 / 1054 * (top - bottom)]
    sample = dict(
        id="bengaluru", title="Bengaluru rooftops",
        description="Eastern Bengaluru apartment blocks · satellite image, January 2019",
        image="/static/samples/bengaluru.png", width=900, height=900,
        ground_pixel_size_m=.5, native_ground_pixel_size_m=1.5,
        center_lon_lat=[(crop_bounds[0] + crop_bounds[2]) / 2, (crop_bounds[1] + crop_bounds[3]) / 2],
        crop_bounds_lon_lat=crop_bounds, original_tile_bounds_lon_lat=BOUNDS,
        original_crop_pixels=CROP, original_file=Path(MEMBER).name,
        source="Airbus DS (2013–2021) / WorldStrat — Cornebise, Oršolić & Kalaitzis (2022)",
        source_url="https://zenodo.org/records/6810792", archive_url=ARCHIVE, archive_member=MEMBER,
        metadata_url="https://zenodo.org/records/6810792/files/metadata.csv?download=1",
        acquisition_date="2019-01-19", license="CC BY-NC 4.0",
        license_url="https://creativecommons.org/licenses/by-nc/4.0/",
        usage_note="Noncommercial educational demonstration. Native detail is approximately 1.5 m; scale and roof boundaries are approximate.",
        modifications="RGB from pansharpened TIFF; global channel-wise 1st/99th percentile stretch; 300×300 source crop bilinearly resampled to 900×900. No generated detail, masks or predictions baked into the image.",
        original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
        sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    manifest_path = ROOT / "static/samples/manifest.json"
    others = [s for s in json.loads(manifest_path.read_text(encoding="utf-8")) if s["id"] not in {"uttari", "bengaluru"}]
    manifest_path.write_text(json.dumps([sample, *others], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Prepared Bengaluru satellite crop; source and checksum recorded in sample manifest.")


if __name__ == "__main__":
    main()
