# RoofTrace Solar: submission answers

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
WHU Building Dataset test image. A pretrained WHU-specific UNet++ model
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

## Demo guide

1. Choose Leafy neighborhood and click Find rooftops.
2. Solar estimates run automatically. Click each highlighted roof for its own result card.
3. Explain roof area, panel count, capacity (kWp) and yearly energy (kWh).
4. Use the monthly chart to show seasonal changes. Export the result if requested.
5. Advanced assumptions stay available; these are screening estimates requiring site review.

The app uses real building segmentation, licensed imagery and free JRC PVGIS climate data.
WHU samples use 0.3 m/pixel and an approximate Christchurch climate scenario; exact tile locations are unavailable. Uploads support up to
2048 pixels per side and 3.5 MB, preserving native image coordinates within that limit.
Google Satellite is a reference link; no paid Google API or Google imagery analysis is used.
