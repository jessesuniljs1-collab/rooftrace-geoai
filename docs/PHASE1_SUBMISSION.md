# RoofTrace Solar: Phase 1 submission

Updated **16 November 2026 (IST)** for the team's requested free solar extension.
The original building-only version is preserved in Git history. The form is unsubmitted.

## Copy-ready fields

**Team Name**

404: JCT Not Found

**Team Leader Name**

Jesse Sunil

**Assigned Problem Statement**

Problem 13 — Satellite Image Intelligence

**Project Title**

RoofTrace Solar — Rooftop Solar Potential from Overhead Imagery

**Live Deployed Application Link**

https://rooftrace-geoai.vercel.app

**Public GitHub Repository Link**

https://github.com/jessesuniljs1-collab/rooftrace-geoai

**Brief Description of Core User Flow and Data Sources Used**

Users upload overhead JPG/PNG imagery or select an attributed sample, including a
georeferenced Bengaluru-area drone image. A pretrained WHU-specific UNet++ model
segments candidate roof regions. Users verify scale and location, adjust panel/roof
assumptions, then estimate per-region panel fit, capacity and annual/monthly energy
using free JRC PVGIS solar-yield data. Interactive roof selection, exclusions,
annotated PNG, building CSV, solar CSV and JSON reports make assumptions reviewable.
Geometry is adapted with attribution from Project Sunroof India. Other samples use
WHU/USGS imagery. Google Satellite is a keyless external reference link; its pixels
are not analyzed in this free implementation.

**Confirmation**

Yes. The application and repository are publicly accessible without evaluator login.
Our original application integrates attributed external model weights, Apache-2.0
Sunroof geometry, licensed imagery and free PVGIS data. We do not claim ownership
of those assets or validated installation suitability. AI coding assistance was used.

The checkbox is supported for that actual scope. Do not describe this as Google-image
analysis, a Google Sunroof product, or a validated engineering design. The team chose
no Google billing. The proposed title reflects the new scope; submit it only if the
hackathon permits updating the earlier project title.

## Handoff

The building-specific model and real inference remain in place. India sample:
DroneMaps.in / Chetan Prasad / Open Imagery Network, Uttari near Bengaluru, acquired
21 July 2022, CC BY 4.0, georeferenced 0.3 m/pixel crop. Other sources: WHU test
samples, USGS imagery and PVGIS ERA5 regional yield. Google is visual context only.

Requested upstream: AKASH2907/project_sunroof_india, Apache-2.0, commit
`0c6426b9c06aa784cfee2860d3a9965c36d9222e`. Scale/rotation functions are adapted,
identified and credited; the original license is preserved. Its Google image examples
are not shipped. See THIRD_PARTY_NOTICES.md.

Defaults: 450 W, 2×1.1 m module, 0.5 m setback, 0.1 m gap, 60% coverage cap,
10° tilt, south-facing in northern hemisphere, 14% system loss, 0% additional shade.
All are scenario assumptions. Roof area comes from segmented pixels × scale²;
capacity from panel count × W/1000; energy from PVGIS specific yield × capacity.

**Verification:** 14 local Python tests and DOM-state checks passed. Real HTTP
checks exercised India inference, PVGIS calculation, area/capacity, exclusions and
threshold changes. CI also builds Docker and exercises real inference. Public solar
verification records are in docs/solar-public-verification.json. A separate
[hosted public-verification run](https://github.com/jessesuniljs1-collab/rooftrace-geoai/actions/runs/43809368898)
passed unauthenticated checks for all five samples, uploads, threshold filtering,
zero results, corrupt-file rejection, oversized-upload HTTP 413, repository visibility,
and the actual solar/PVGIS flow. Its JSON records are committed in docs/.

Actual India example: **2 roof regions, 29 illustrative panels, 13.05 kWp,
19,499.4 kWh/year**, PVGIS ERA5 2005–2023, default scenario. These are calculated
screening outputs, not measured electricity. docs/solar-india-smoke.png is a recorded
smoke-test artifact, never substituted for fresh predictions in the app.

**Visual verification limitation:** browser automation stopped because it could not
confidently identify the browser URL. The updated solar UI was not visually verified.
API, syntax and DOM-state checks do not establish visual/mobile layout quality.
Older building-only desktop/phone screenshots are historical evidence only.

Other limits: regions may merge houses or split roofs; image scale/location must be
correct; 2D layouts do not measure pitch, obstacles, local shade, load capacity or
local installation requirements. PVGIS represents regional climate/terrain, not
property-level shading. No ground-truth energy, payback, subsidy or savings claims.

Uploads remain 3.5 MB, 64–1024 pixels/side. Solar allows 200 regions/5,000 panel
illustrations. Free hosting/PVGIS can cold-start or fail; failures are explicit.
No API secrets are required. Full-history, redacted secret scanning runs in CI.

Deployment is through the authenticated Vercel CLI. Automatic GitHub deployment
linking remains unavailable with current integration permissions. Use the stable
production URL above, not an authenticated preview URL. Submit the form yourself.
