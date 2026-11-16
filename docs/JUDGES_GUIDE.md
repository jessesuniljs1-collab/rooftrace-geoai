# RoofTrace Solar: a one-minute demo

1. Choose **Leafy neighborhood**, then **Find rooftops**.
2. Wait for building detection and the automatic solar estimate.
3. Click each highlighted roof. Point out the card showing area, panels, capacity and annual electricity.
4. Show the monthly chart, then export solar CSV or JSON.
5. Open settings only if judges ask about assumptions.

## What to say

“RoofTrace turns an overhead image into a first-pass solar opportunity assessment.
Our building model finds candidate roof regions. We use image scale to estimate
area and fit illustrative panels within those regions. Free JRC PVGIS climate data
estimates monthly and annual generation. Every roof can be inspected individually,
and results can be downloaded for review.”

## Four useful answers

- **Where is the AI?** A pretrained UNet++ building-segmentation model identifies roof pixels. We integrate it; we did not train the checkpoint.
- **What do the numbers mean?** m² is projected roof area; kWp is installed panel power; kWh/year is estimated yearly electricity.
- **Is this installation-ready?** It is screening. An installer must verify roof structure, local shadows, obstacles and electrical requirements.
- **Are you analyzing Google images?** This free version analyzes licensed imagery or uploads. Google Satellite is an external visual reference. We use no paid Google API.

## Avoid these claims

Do not claim guaranteed production, exact individual-house counts, measured shade,
installation approval, financial savings, or that our team created the external model/data.
WHU samples use an approximate Christchurch climate scenario because exact tile coordinates are unavailable. Changing a location field does not move the image.
