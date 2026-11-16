# RoofTrace Solar

**Rooftop solar screening from overhead imagery**

[![Application checks](https://github.com/jessesuniljs1-collab/rooftrace-geoai/actions/workflows/checks.yml/badge.svg)](https://github.com/jessesuniljs1-collab/rooftrace-geoai/actions/workflows/checks.yml)
[![Application license: MIT](https://img.shields.io/badge/Application-MIT-24664d)](LICENSE)

[**Launch application**](https://rooftrace-geoai.vercel.app) · [Presentation guide](docs/JUDGES_GUIDE.md) · [Submission details](docs/PHASE1_SUBMISSION.md)

RoofTrace Solar identifies candidate building regions in aerial or satellite images
and estimates their solar panel capacity and energy production. An interactive
viewer connects each roof region to its area, illustrative panel layout and solar
estimate, with editable assumptions and downloadable results.

Developed by **404: JCT Not Found** for **IEEE Week 2026 GeoAI Hackathon**,
Problem 13 — Satellite Image Intelligence.

## Application preview

![Leafy neighborhood: original overhead imagery and real model predictions, with 56 connected building regions at probability threshold 0.50](docs/rooftrace-solar-preview.png)

*Leafy neighborhood sample: 56 connected regions at probability threshold 0.50.
The right image contains actual UNet++ predictions, recorded for this README.
Connected regions can merge adjoining homes or fragment a roof; this is not a
verified count of individual houses. Image: WHU Building Dataset / Ji, Wei & Lu
(2019), hosted by giswqs under CC BY 4.0. RoofTrace added the mask, boxes and labels.
The application computes fresh predictions when analysis starts.*

## Core workflow

1. **Choose imagery.** Select a sample or upload an overhead JPG/PNG.
2. **Find rooftops.** Run the building model and review its annotated regions.
3. **Inspect solar potential.** Click a roof for area, panel count, capacity in kWp
   and estimated annual electricity in kWh. Sample estimates run automatically.
4. **Refine assumptions.** Adjust probability threshold, exclude incorrect regions,
   or change location, image scale and panel settings.
5. **Export.** Download an annotated PNG, building CSV, per-roof solar CSV or JSON report.

Uploads support **64–2048 pixels per side** and **3.5 MB**. For uploaded imagery,
provide its real ground scale and location; ordinary images do not supply those
measurements automatically. Images are processed in memory and not retained.

## Method and architecture

| Component | Implementation |
| --- | --- |
| Building segmentation | External WHU-specific UNet++ / EfficientNet-B4 checkpoint |
| CPU inference | Checksum-pinned ONNX model; overlapping 512 px tiles |
| Region extraction | Connected building pixels; minimum region area of 16 pixels |
| Solar panel scenarios | Mask-contained placement with module dimensions, setbacks and coverage limits |
| Energy estimates | Free European Commission JRC PVGIS 5.3 regional solar yield |
| Application | FastAPI, ONNX Runtime, OpenCV, HTML, CSS and JavaScript |
| Deployment | Single Vercel service; Docker configuration for self-hosting |

The viewer and exports share the active probability threshold and original-image
pixel coordinates. A stateless request flow keeps users' uploaded images and
results isolated. No paid API or Google credential is required.

## Run locally

Requirements: **64-bit Python 3.12**, CPU, approximately **1–2 GB available RAM**,
and internet access for model setup and solar-weather requests.

```sh
git clone https://github.com/jessesuniljs1-collab/rooftrace-geoai.git
cd rooftrace-geoai
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/download_model.py
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The `/health` endpoint reports runtime readiness.
Optional environment settings are documented in [.env.example](.env.example).

```sh
docker build -t rooftrace .
docker run --rm -p 8000:8000 rooftrace
```

Model acquisition, conversion, coordinate conventions, evaluation methodology and
deployment configuration are documented in the [technical reference](docs/TECHNICAL_REFERENCE.md).

## Imagery, model and attribution

| Resource | Source and reuse terms |
| --- | --- |
| Building checkpoint | giswqs WHU UNet++ / EfficientNet-B4; Apache-2.0 |
| Bengaluru satellite sample | WorldStrat / Airbus DS; CC BY-NC 4.0; noncommercial educational use |
| Leafy neighborhood and two other aerial samples | WHU test release hosted by giswqs; CC BY 4.0 |
| Phoenix satellite/aerial sample | Public-domain USGS imagery |
| Solar yield | European Commission JRC PVGIS; acknowledge in derived reports |
| Adapted geometry functions | AKASH2907 Project Sunroof India; Apache-2.0 |

The Bengaluru scene shows apartment blocks in eastern Bengaluru on **19 January
2019**. Native detail is approximately **1.5 m/pixel**. Bilinear output sampling at
**0.5 m/pixel** aids processing and display without adding satellite detail.
Estimated areas and boundaries remain approximate.

The [sample manifest](static/samples/manifest.json) records exact sources, hashes,
locations and image transformations. [Third-party notices](THIRD_PARTY_NOTICES.md)
and [preserved licenses](licenses) specify the applicable terms. The MIT license
covers RoofTrace's original source code; it does not relicense third-party assets.
Google Satellite is an external location-reference link; Google pixels are not
fetched or analyzed in this free implementation.

## Verification and limitations

Automated checks cover image validation, coordinate alignment, region filtering,
solar geometry, export consistency and request isolation. GitHub Actions also
builds the Docker application and performs real inference. Public smoke checks
exercise samples, uploads and live PVGIS calculations.

- Regions are model predictions, not cadastral boundaries or verified house counts.
- Resolution, shadows, viewing angle and adjoining roofs affect detection quality.
- Solar layouts are **screening scenarios**, not validated installation designs.
  Roof pitch, obstacles, structural strength and nearby shade are not measured.
- Regional climate estimates cannot guarantee a particular roof's production.
- The Bengaluru sample has no labeled accuracy benchmark; no Bengaluru precision,
  recall or measured solar-production accuracy is claimed.
- Free hosting can have cold starts. Inference and PVGIS requests require connectivity.

See the [technical reference](docs/TECHNICAL_REFERENCE.md) and recorded verification
reports in [docs](docs) for measured results and their scope.

## Team and original contribution

**404: JCT Not Found** — Jesse Sunil (team leader), Charan SC and SM Tejashree Kashyap.

The team's application integrates building inference, aligned tiling, interactive
roof inspection, solar scenarios, PVGIS calculations, exports and deployment.
The building checkpoint was pretrained externally; we did not train it. External
code and data are attributed above. AI coding assistance was used.
