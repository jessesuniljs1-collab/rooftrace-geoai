# RoofTrace

**Building Detection from Satellite Imagery · IEEE Week 2026 GeoAI Hackathon**

Team **404: JCT Not Found** — Jesse Sunil (leader), Charan SC,
SM Tejashree Kashyap. Assigned **Problem 13 — Satellite Image Intelligence**.

RoofTrace estimates visible building **regions** in overhead RGB images, draws
their bounding boxes on the original image, and exports an annotated PNG and
structured CSV. Every analysis runs the actual building-specific neural network.

- [Public source repository](https://github.com/jessesuniljs1-collab/rooftrace-geoai)
- [Live public application](https://rooftrace-geoai.vercel.app)
- Live URL and verified submission answers: [`docs/PHASE1_SUBMISSION.md`](docs/PHASE1_SUBMISSION.md)
- [Model artifact and conversion manifest](https://github.com/jessesuniljs1-collab/rooftrace-geoai/releases/tag/model-v1)

## Core user flow

1. Select one of three WHU test images, explore the lower-resolution USGS transfer
   challenge, or upload your own JPG/PNG.
2. Select **Analyze image**. Loading feedback remains visible while fresh CPU
   inference runs. No reference labels or saved predictions are served.
3. Inspect the original and annotated views, estimated connected-region count,
   dimensions, timing, region bounds and mean building probabilities.
4. Adjust the **building probability threshold** from 0.10 to 0.90. The probability
   map from this analysis is re-thresholded without re-running the network. The
   count, viewer, scores and both exports update together. Downloads are disabled
   while filtering is pending.
5. Download an **annotated PNG** and **results CSV**, or reset to analyze another image.

## Run locally

Use 64-bit Python **3.12**, a CPU, approximately 1–2 GB of available RAM, and internet
access for package installation and the initial 80 MB model download. No API key,
GPU, paid inference service or user account is needed.

```sh
git clone https://github.com/jessesuniljs1-collab/rooftrace-geoai.git
cd rooftrace-geoai
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/download_model.py
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. `/health` checks application readiness and model file
presence. The first inference verifies its SHA-256 and loads the model. If acquisition
fails, retry the download script; it verifies and atomically installs the artifact.

```sh
docker build -t rooftrace .
docker run --rm -p 8000:8000 rooftrace
```

The Docker image uses an unprivileged user and includes a health check. Optional
settings, shown with placeholder/default values in `.env.example`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ROOFTRACE_THREADS` | `2` | ONNX CPU intra-operation threads |
| `ROOFTRACE_MODEL_PATH` | `models/rooftrace-whu.onnx` | Custom absolute artifact path; same manifest checksum required |

Set variables in your shell or hosting environment. `.env` is not automatically
loaded. There are **no application secrets** to configure.

## Model and processing

RoofTrace uses [giswqs's WHU building model](https://huggingface.co/giswqs/whu-building-unetplusplus-efficientnet-b4),
revision `09df9efd323bbd3d56b98b4857129eb9b5baa2d3`: **UNet++ with an
EfficientNet-B4 encoder**, approximately 20.8 million parameters, background and
building semantic classes. It takes three-band RGB, 512×512, float32 values divided
by 255. No ImageNet mean/std normalization is applied; this follows the publisher's
training and inference implementation. Its nominal training scale is 0.3 m/pixel.

The publisher reports training on WHU imagery using ImageNet encoder initialization,
AdamW, cross-entropy loss and early stopping. These are upstream details, not a
RoofTrace training run. **We did not fine-tune the model.**

We strictly loaded the checkpoint and exported it to **ONNX opset 17**. The export
parity check on a seeded 512×512 RGB tensor measured maximum absolute logit error
`0.0000124` against PyTorch. Exact hashes, tensor contracts and artifact size
(`80,031,750` bytes) are in [`models/manifest.json`](models/manifest.json).
The export is Apache-2.0 licensed. To reproduce conversion in a separate environment:

```sh
python -m pip install -r requirements.txt -r requirements-export.txt
python scripts/export_model.py
```

For a CPU-only PyTorch installation, install torch/torchvision from
`https://download.pytorch.org/whl/cpu` first. Conversion may yield a different
binary checksum on different exporter/library platforms; verify numerical parity
and update the manifest and release together before deploying a new conversion.

### Tiling, region meaning and coordinates

- JPEG/PNG decode, EXIF orientation, RGB conversion; transparent pixels composite
  onto white. Images are never globally resized for inference.
- Tile size **512**, stride **384**, nominal overlap **128** pixels. The last tile
  anchors to the image edge, so overlap can be larger. Smaller images use reflected
  padding, cropped away after prediction.
- Two-class softmax yields building probabilities. Predictions are accumulated in
  original pixel coordinates and averaged in overlaps **before** region extraction,
  so tile duplicates do not inflate counts.
- The merged map is rounded to 8-bit probabilities (`round(p × 255)`), transferred
  losslessly as a PNG, and thresholded consistently on the server for all updates.
  This introduces at most ~0.002 probability rounding error.
- **8-connected components** of at least **16 pixels** become building regions.
  No watershed or invented instance separation is used. Adjoining roofs may merge;
  one roof can fragment. Raising the threshold can either increase or decrease
  the count. This is an estimate of regions, not verified building instances.
- Each score is the **mean building-pixel probability inside the component**,
  not a calibrated object-detection confidence.
- Boxes use original EXIF-oriented image pixels: origin at top-left, x to the right,
  y down; **half-open bounds** `[x_min, x_max)` and `[y_min, y_max)`. The right and
  bottom bounds can equal image width and height. Area is segmented pixel count,
  not bounding-box area or ground area.

CSV columns: `image_id`, `detection_id`, `class`, `x_min`, `y_min`,
`x_max_exclusive`, `y_max_exclusive`, `area_pixels`, `mean_building_probability`,
`active_probability_threshold`, `model_id`. Empty detections produce a valid
header-only CSV. The annotated PNG uses the same active regions and region-ID
setting as the viewer. Downloading PNG always includes annotations, even while
the original comparison tab is selected.

## Data and attribution

The model was trained upstream on the **WHU Building Dataset**, not SpaceNet.
Demo images are `test_0002`, `test_0006` and `test_0003` from the hosted WHU
**test** split: courtyard housing, a leafy neighborhood and farmland. The hosted
dataset release declares **CC BY 4.0**. They are distributed unchanged, renamed
for the interface, and credited to **Ji, Wei & Lu (2019), Wuhan University**, via
the giswqs release. This is an educational research demonstration; consult the
original provider before commercial reuse. The original WHU site was inaccessible
during implementation, and its terms should not be assumed identical to the mirror.

The separate **Phoenix** challenge chip is public-domain **USDA/USGS The National
Map** imagery. Its requested sampling is 0.3 m/pixel but native imagery is coarser;
upsampling does not add roof detail. It demonstrates substantial transfer errors.
Its acquisition year is not asserted, and it has no local reference labels.

Exact source URLs, revisions, bounds (where available) and checksums are recorded in
[`static/samples/manifest.json`](static/samples/manifest.json).
`python scripts/fetch_samples.py` fetches only these four images. Neither an entire
dataset nor any label masks are included in the app. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for license scope and provenance.

## Architecture and limits

One **FastAPI** service serves responsive HTML/CSS/JavaScript and CPU inference
using **ONNX Runtime**, NumPy, Pillow and OpenCV. PyTorch is needed only for export.
This change from the proposed PyTorch runtime keeps serverless dependencies and
cold-start size manageable. The proposed fine-tuned YOLO/SpaceNet pipeline was
replaced with an available, tested building-specific segmentation model.

- `GET /`, `GET /static/*`: UI and attributed samples.
- `GET /health`: readiness metadata; returns 503 when the model is missing.
- `GET /api/samples`: sample metadata.
- `POST /api/analyze`: multipart `file` **or** `sample_id`, plus `threshold`.
  Returns dimensions, model, timing, regions and an encoded probability map.
- `POST /api/regions`: JSON `probability_png`, `threshold`; stateless filtering.

Uploads are restricted to **3,500,000 bytes**, **64–1024 pixels per side**, and
**1,048,576 pixels total**. Upload request bodies are bounded before multipart
parsing. Animated images, corrupt decodes and unsupported formats are rejected.
Large scenes must be cropped before upload; supported larger images use tiling.
At most 5,000 retained regions are allowed per image. One inference at a time is
allowed per process to bound memory; simultaneous users may receive a clear busy
response and can retry. Each request has its own image and result arrays. Uploads
are not written to disk or logged, and no user result database exists. Probability
maps remain in browser memory for filtering and are cleared by reset/navigation.
Image requests are `no-store`; the host can still retain ordinary access metadata.

JPG/PNG lack reliable georeferencing or ground scale. No GIS coordinates, cadastral
accuracy, building completeness, or worldwide generalization is claimed. Resolution,
obliquity, occlusion, tree cover and shadows can materially alter results. Free
hosting can cold-start or hit account usage limits. First inference can take longer.

## Verification and measured evaluation

```sh
python -m pip install -r requirements-dev.txt
python scripts/download_model.py
ruff check .
node --check static/app.js
pytest -q
python scripts/evaluate.py  # optional: fetches six labeled test tiles into private/
```

GitHub Actions runs the real checks, including acquisition/checksum verification,
real sample/upload inference, zero detections, filtering, image validation,
non-square tiling/alignment, original coordinates and concurrent request isolation.
Synthetic masks and a deterministic pixel model are used **only in tests** to
check coordinate transformations. They are never used in the public inference flow.

Our six-tile diagnostic at pixel probability **0.50**, minimum region area **16**,
greedy one-to-one **mask IoU ≥ 0.50** region matching measured:

| Measurement | Result |
| --- | --- |
| Region precision | 87.35% (145 / 166) |
| Region recall | 87.88% (145 / 165) |
| Mean absolute region-count error per tile | 1.17 |
| Pixel precision / recall | 94.80% / 93.35% |
| Median warm 512×512 inference | 0.639 seconds on local CPU, 2 threads |

The first six lexicographic WHU test tiles were selected before inference. Threshold
0.50 is a conventional fixed default, **not validation-fitted**. No training or
test-set threshold optimization was done. Both predictions and reference masks
become 8-connected regions with the same area filter. Reference regions may themselves
join buildings. The six nearby tiles are a **small diagnostic**, not a broad or
independently audited geographic benchmark. The model publisher's full-test scores
are not presented as RoofTrace measurements. Public sample selection overlaps this
diagnostic, and the USGS transfer scene is not covered by these accuracy values.
Actual per-image measurements and hardware are in [`docs/evaluation.json`](docs/evaluation.json).

## Deployment

The authenticated destination is **Vercel Hobby** (`kodiak-opr-t1`), with Python 3.12,
the FastAPI preset and a 120-second function ceiling. `vercel.json` downloads the
checksum-pinned model at build time. The model is included in the deployed function;
no runtime Hub token, persistent volume or per-analysis model download is required.
Deploy with `vercel --prod --yes --scope kodiak-opr-t1` after linking your own project.
Keep production access public; preview deployments can have a different policy.

This personal hackathon deployment uses free-tier resources. No paid plan or
add-on is required. Deploy on another Docker-capable CPU host if free-tier limits
are unsuitable. See the Phase 1 handoff for the actually verified URL, workflow
status, public inference checks and remaining delivery limitations.

## License

Team-authored application source is **MIT**. The pretrained model and ONNX export
are **Apache-2.0**. WHU samples use the hosted release's **CC BY 4.0** declaration;
the USGS sample is public domain. These third-party assets and their attributions
are explicitly outside the MIT source-code grant.
