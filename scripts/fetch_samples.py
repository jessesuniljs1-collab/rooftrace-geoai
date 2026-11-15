"""Fetch three WHU test images and one USGS transfer challenge, with provenance."""
import hashlib
import io
import json
import math
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SERVICE = "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer"
SCENES = [
    ("phoenix", "Phoenix mixed blocks", -112.0670, 33.4700, "Larger buildings beside smaller homes"),
]


def main():
    folder = ROOT / "static" / "samples"
    folder.mkdir(parents=True, exist_ok=True)
    manifest = []
    revision = "c9ccc03ef4dd004b63cf179835771ab5e074bd3d"
    scenes = [(2, "courtyard", "Courtyard housing", "Adjoining roofs and a central courtyard"),
              (6, "neighborhood", "Leafy neighborhood", "Detached homes, shadows and varied roofs"),
              (3, "farmland", "Fields & roadside", "Mostly vegetation with a roof at the image edge")]
    for number, identifier, title, detail in scenes:
        source = f"https://huggingface.co/datasets/giswqs/WHU-Building-Dataset/resolve/{revision}/test/Image/test_{number:04d}.png"
        response = requests.get(source, timeout=120)
        response.raise_for_status()
        path = folder / f"{identifier}.png"
        path.write_bytes(response.content)
        manifest.append(dict(id=identifier, title=title, description=detail,
                             image=f"/static/samples/{identifier}.png", width=512, height=512,
                             ground_pixel_size_m=0.3, source="WHU Building Dataset / Ji, Wei & Lu (2019), hosted by giswqs",
                             source_url=source, split="test", original_file=f"test_{number:04d}.png",
                             license="CC BY 4.0 per the hosted dataset release; research demonstration",
                             license_url="https://creativecommons.org/licenses/by/4.0/",
                             sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    for identifier, title, lon, lat, detail in SCENES:
        x = 6378137 * math.radians(lon)
        y = 6378137 * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
        # 153.6 ground metres across at the latitude of each scene, 512 RGB pixels.
        half = 76.8 / math.cos(math.radians(lat))
        bbox = [x - half, y - half, x + half, y + half]
        params = dict(bbox=",".join(map(str, bbox)), bboxSR=3857, imageSR=3857,
                      size="512,512", format="png", transparent="false", f="image")
        response = requests.get(f"{SERVICE}/export", params=params, timeout=120)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        image.save(folder / f"{identifier}.png")
        manifest.append(dict(id=identifier, title=title, description=detail,
                             image=f"/static/samples/{identifier}.png", width=512, height=512,
                             center_lon_lat=[lon, lat], bbox_3857=bbox,
                             requested_ground_pixel_size_m=0.3,
                             note="Service resampling; native imagery resolution varies, typically 1 m. Acquisition year is not asserted.",
                             source="USDA / USGS The National Map: Orthoimagery",
                             source_url=response.url, license="Public domain",
                             sha256=hashlib.sha256((folder / f"{identifier}.png").read_bytes()).hexdigest()))
        print(identifier, image.size, len(response.content))
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()

