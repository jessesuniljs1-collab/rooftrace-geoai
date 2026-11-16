"""Prepare one CC-BY OAM India chip. Extra prep-only deps: rasterio, pyproj."""
import hashlib
import json
import sys
from pathlib import Path

import rasterio
import requests
from PIL import Image
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[1]


def main():
    metadata_url = "https://api.openaerialmap.org/meta/62f32995f526a800059dc272"
    response = requests.get(metadata_url, timeout=30)
    response.raise_for_status()
    entry = response.json()["results"]
    if isinstance(entry, list):
        entry = entry[0]
    folder = ROOT / "private/india"
    folder.mkdir(parents=True, exist_ok=True)
    original = folder / "uttari.tif"
    if not original.exists():
        response = requests.get(entry["uuid"], timeout=120)
        response.raise_for_status()
        original.write_bytes(response.content)
    with rasterio.open(original) as source:
        extent = 512 * .3 / abs(source.transform.a)
        # Fixed crop around the visible farmstead; choice made for a useful demonstration.
        center_col, center_row = (2400, 3300) if len(sys.argv) == 1 else (int(sys.argv[1]), int(sys.argv[2]))
        window = Window(center_col - extent / 2, center_row - extent / 2, extent, extent)
        rgb = source.read([1, 2, 3], window=window, out_shape=(3, 512, 512), resampling=Resampling.bilinear)
        east, north = source.transform * (center_col, center_row)
        lon, lat = Transformer.from_crs(source.crs, "EPSG:4326", always_xy=True).transform(east, north)
        bounds = rasterio.windows.bounds(window, source.transform)
    target = ROOT / "static/samples/uttari.png"
    Image.fromarray(rgb.transpose(1, 2, 0)).save(target)
    manifest_path = ROOT / "static/samples/manifest.json"
    manifest = [item for item in json.loads(manifest_path.read_text()) if item["id"] != "uttari"]
    sample = dict(id="uttari", title="Bengaluru farmstead", description="Open drone imagery, Uttari near Bengaluru, India",
                  image="/static/samples/uttari.png", width=512, height=512,
                  ground_pixel_size_m=.3, center_lon_lat=[lon, lat], crop_bounds_utm43n=list(bounds),
                  source="DroneMaps.in / Chetan Prasad / Open Imagery Network",
                  source_url=entry["uuid"], metadata_url=metadata_url,
                  acquisition_date=entry["acquisition_start"], license="CC BY 4.0",
                  license_url="https://creativecommons.org/licenses/by/4.0/",
                  modifications="Cropped and bilinearly resampled from 0.04832 m/pixel UTM imagery to 0.3 m/pixel. No prediction is baked into the image.",
                  sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    manifest_path.write_text(json.dumps([sample, *manifest], indent=2) + "\n")
    print(json.dumps(sample, indent=2))


if __name__ == "__main__":
    main()
