# RoofTrace Solar

**Rooftop solar-potential screening from overhead imagery**

IEEE Week 2026 GeoAI Hackathon · Problem 13 — Satellite Image Intelligence.
Team **404: JCT Not Found**: Jesse Sunil (leader), Charan SC, SM Tejashree Kashyap.

[Live application](https://rooftrace-geoai.vercel.app) · [Public source](https://github.com/jessesuniljs1-collab/rooftrace-geoai) · [Submission answers](docs/PHASE1_SUBMISSION.md) · [Model artifact](https://github.com/jessesuniljs1-collab/rooftrace-geoai/releases/tag/model-v1)

RoofTrace combines building-specific neural segmentation, physical image scale,
mask-contained panel scenarios and free **European Commission JRC PVGIS** solar
calculations. It estimates each **roof region's** panels, DC capacity and annual/monthly
AC energy. A connected region is not guaranteed to be an individual house.

The team explicitly selected the **free implementation**. Google Satellite is an
external visual-reference link using documented, keyless Maps URLs. **Google pixels
are not downloaded or analyzed. No Google Solar API, billing account, Google API key,
OpenAI API key or paid inference API is used.**

## Core flow

1. Choose an attributed image or upload JPG/PNG. The default sample is a georeferenced
   **Uttari farmstead near Bengaluru, India**.
2. Select **Find rooftops** for real building inference. Inspect original/annotated
   views, estimated region counts, scores, coordinates and probability threshold.
3. Confirm **ground scale and location**. Samples supply these where known. For uploads,
   enter them or calibrate scale from two points and a real measured distance.
4. Review module dimensions/rating, edge setback, gaps, roof coverage, tilt, azimuth,
   system losses and extra shade-loss assumptions.
5. Sample solar estimates run automatically after roof detection. For uploads, select **Calculate solar potential** after entering scale/location. The solver fits panel illustrations inside
   predicted masks and obtains a real regional **1 kWp PVGIS** calculation.
6. Select a roof in the ranked selector or click its box to inspect its area, panels,
   capacity and annual/monthly energy. Exclude false-positive regions and recalculate.
7. Download annotated PNG, building CSV, solar CSV or JSON. Threshold/settings changes
   clear stale solar results and disable their downloads. Reset starts a new scene.

## Local setup

Use 64-bit **Python 3.12**, CPU, approximately **1–2 GB available RAM**, and internet
for packages/model setup and PVGIS calculations. No GPU or account is required.

```sh
git clone https://github.com/jessesuniljs1-collab/rooftrace-geoai.git
cd rooftrace-geoai
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/download_model.py
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The download script atomically installs a SHA-256-verified
model. `/health` checks model presence; first inference verifies the hash and loads it.

```sh
docker build -t rooftrace .
docker run --rm -p 8000:8000 rooftrace
```

Docker includes model setup, an unprivileged user and health check. Optional settings:
`ROOFTRACE_THREADS=2`; `ROOFTRACE_MODEL_PATH=/absolute/path/to/rooftrace-whu.onnx`
with the same manifest checksum. `.env.example` has placeholders; `.env` is not
loaded automatically. There are no application secrets.

## Building model and alignment

External [WHU checkpoint](https://huggingface.co/giswqs/whu-building-unetplusplus-efficientnet-b4),
revision `09df9efd323bbd3d56b98b4857129eb9b5baa2d3`: **UNet++ / EfficientNet-B4**,
background/building classes, approximately 20.8M parameters, Apache-2.0. Inputs:
**512×512 RGB float32 / 255**, no ImageNet mean/std normalization, following the
publisher's implementation. Nominal training scale: **0.3 m/pixel**, WHU imagery.
The team did not train or fine-tune the model; no generic COCO detector is used.

Production uses an **80,031,750-byte ONNX opset 17** export. Seeded conversion parity
against PyTorch measured max absolute logit error **0.0000124**. Hashes and tensor
contract: [`models/manifest.json`](models/manifest.json).

```sh
# Optional, separate conversion environment:
python -m pip install -r requirements.txt -r requirements-export.txt
python scripts/export_model.py
```

For CPU PyTorch, install torch/torchvision from `https://download.pytorch.org/whl/cpu`
first. Different exporter platforms may change binary hashes; verify parity and
update the manifest/release together before deploying another conversion.

Images are decoded, EXIF-oriented and converted to RGB; transparency composites
onto white. No global inference resize occurs. Supported large images use **512 px
tiles, stride 384**, reflected edge padding and overlap-averaged softmax probabilities
in original coordinates. Components are extracted after stitching, avoiding tile
duplicates. Maps are rounded once to 8-bit and transferred losslessly as PNG;
probability rounding error is at most about 0.002.

**8-connected regions, minimum 16 pixels**, become candidate roofs. Adjoining houses
may merge and one house may split. Scores are mean pixel probabilities, not calibrated
object confidence. Threshold increases may raise or lower region counts. Coordinates:
original EXIF-oriented pixels, origin top-left, x right/y down, **half-open bounds**
`[x_min,x_max)` / `[y_min,y_max)`. Area means segmented pixels, not box area.

## Solar methodology

The requested [Project Sunroof India](https://github.com/AKASH2907/project_sunroof_india)
commit `0c6426b9c06aa784cfee2860d3a9965c36d9222e` supplies attributed **Apache-2.0**
Mercator-scale and rotation code adapted in `rooftrace/sunroof_geometry.py`. The
original license is preserved. Its image examples/results are not redistributed.
New mask packing, web interface, PVGIS integration and reports are RoofTrace work.

`projected_roof_m2 = segmented_pixels × meters_per_pixel²`.

Scale must be verified: 10% scale error changes area by approximately 21%. Sample
metadata supplies known scale; uploads do not. WHU's default Christchurch-area
climate scenario is explicitly approximate because exact tile coordinates are
unavailable. Changing location does not move the image or validate local accuracy.

The mask is eroded by the edge setback. The solver searches **0°,30°,60°,90°** grid
rotations with four offsets each. Physical panel footprints and gaps are rounded
up to pixels, and every rasterized panel must remain inside the eroded mask,
including around holes. A coverage cap limits panel count. This is a conservative
**2D flat-roof illustration**, not an optimal 3D design or detected existing panels.
Tilt affects energy, not 2D layout. Coverage is an assumption, not measured clear area.

Defaults: **450 W**, **2×1.1 m** modules, **0.5 m** setbacks, **0.1 m** gaps,
**60%** coverage. These are editable generic assumptions, not a manufacturer's
product specification or a claim of local code compliance.

The official **PVGIS 5.3 PVcalc API**, **PVGIS-ERA5**, models crystalline silicon,
ventilated/free mounting, entered tilt/azimuth/losses and terrain horizon. One **1 kWp**
calculation is reused across roofs. Coordinates are rounded to **0.01°**. Returned
database/year ranges are displayed. Cache: memory only, at most 128 scenarios,
24 hours. No images go to PVGIS. No key, account or billing is used.

`capacity_kWp = panel_count × module_watts / 1000`

`annual_AC_kWh = capacity_kWp × PVGIS_specific_yield × (1 − extra_shade_loss)`

Monthly outputs use actual PVGIS monthly specific yields; rounding can differ slightly.
Default system loss is **14%**, additional shade loss **0%** until entered. Nearby
shade, true pitch, obstacles, structural suitability and installation requirements
are not measured. No savings/payback/subsidy claims are made. PVGIS failure produces
an explicit error, never invented yield. Zero-panel cases skip weather and export zeros.

## Data and licenses

- **India/Uttari:** DroneMaps.in / Chetan Prasad / Open Imagery Network, **CC BY 4.0**,
  acquired **21 July 2022**. A 102.4 m UTM-zone-43N crop is bilinearly resampled from
  0.04832 m/pixel to 512×512 at **0.2 m/pixel**. Black survey-edge no-data remains.
- **Three WHU test images:** `test_0002`, `test_0006`, `test_0003`, hosted release
  **CC BY 4.0**, credited to Ji, Wei & Lu (2019), Wuhan University, via giswqs.
  Not RoofTrace training data. The original WHU site was inaccessible; its historical
  research terms may differ from the mirror. Re-check before commercial reuse.
- **Phoenix challenge:** public-domain USDA/USGS The National Map. Requested sampling
  0.3 m/pixel, coarser native detail, substantial transfer errors, acquisition year unverified.
- **PVGIS:** European Commission JRC free regional solar-yield data; acknowledge it
  in derived reports. **Google:** external visual-context link only.

Exact URLs, licenses, crop bounds, modifications, hashes: [`static/samples/manifest.json`](static/samples/manifest.json)
and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). No full dataset or masks ship
with the app. `scripts/fetch_samples.py` fetches WHU/USGS images and preserves an
existing India entry. India reproduction needs prep-only `rasterio==1.4.3 pyproj==3.7.2`,
then `python scripts/fetch_india_sample.py`; these are not runtime dependencies.

## Exports, architecture and privacy

Annotated PNG includes current regions/IDs and any active panel illustration.
Building CSV includes image/region/class, half-open pixel bounds, segmented area,
mean probability, active threshold and model ID; zero detections produce header-only CSV.
Solar CSV includes per-roof area, exclusion, panels, capacity, annual/monthly energy,
scale/location, physical assumptions, PVGIS provenance and model. JSON also includes
panel coordinates and full scenario metadata.

One **FastAPI** service serves HTML/CSS/JS, **ONNX Runtime CPU**, OpenCV geometry and
stdlib HTTP requests to PVGIS. PyTorch is export-only. Main routes:

| Route | Purpose |
|---|---|
| `/`, `/static/*` | Interface and samples |
| `GET /health` | Version/model presence |
| `GET /api/samples` | Sources and metadata |
| `POST /api/analyze` | Multipart image or sample plus threshold |
| `POST /api/regions` | Stateless probability-map filtering |
| `POST /api/solar` | Current probability PNG, threshold, SolarSettings |

Uploads: **3,500,000 bytes**, **64–2048 px/side**, **4,194,304 total pixels**. JPG/PNG
only; corrupt/animated/unsupported images are rejected. Crop bigger scenes first.
Building outputs allow 5,000 components; solar allows **200 regions/5,000 panels**.
One analysis per process bounds resource use; contention returns a retry message.

Images/results are request-local, not written to disk or logged. Browser memory
holds current probability/scenario data until reset/navigation. API responses are
`no-store`. PVGIS receives rounded coordinates and numeric settings, not imagery.
The host may retain ordinary access metadata. Reports contain entered coordinates.

No API secrets are required or exposed. CLI credentials remain outside source.
Environment/key/credential files are ignored. **Gitleaks 8.30.1** scans full history
in CI with redacted findings. The initial history/source/deployed-asset/CI audit
found no exposed keys; see [`docs/security-audit.json`](docs/security-audit.json).
Pattern scans cannot guarantee absence of every possible secret format.

## Verification

```sh
python -m pip install -r requirements-dev.txt
python scripts/download_model.py
ruff check .
node --check static/app.js
node --check static/solar.js
pytest -q
python scripts/verify_solar.py http://127.0.0.1:8000
```

**14 Python tests** cover real sample/upload inference, zeros, validation, tiling/
coordinates, filtering, isolation, solar arithmetic, holes/setbacks, exclusions,
no-weather zero capacity and explicit weather failure. CI also runs jsdom **DOM-state**
checks for solar CSV, threshold/settings invalidation and reset, then builds Docker
and exercises real inference. Explicit test fixtures are never production predictions.

## Deployment

Public service: **Vercel Hobby**, Python 3.12, FastAPI preset, 120-second function
ceiling. The build downloads pinned ONNX weights; no runtime Hub token/volume.
Free hosting/PVGIS can cold-start, rate-limit or fail. Deploy through authenticated
CLI: `vercel deploy --prod --yes --scope kodiak-opr-t1` after project linking.
Automatic GitHub-to-Vercel linking was unavailable with current permissions; CLI
and CI work independently. No paid plan or add-on is required.

Original application: **MIT**. Model/ONNX and adapted Sunroof geometry: **Apache-2.0**.
OAM/hosted WHU imagery: separately attributed **CC BY 4.0**; USGS: public domain.
Third-party assets remain outside the MIT grant.
