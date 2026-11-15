# Third-party attribution and provenance

RoofTrace's UI, API, tiling and alignment, region extraction, exports, validation,
tests and deployment integration are original application work by team
**404: JCT Not Found**, developed with AI coding assistance. The pretrained
network, libraries and imagery below are external. The team did not train this
checkpoint or create the reference labels. No reference mask is used in the app.

## Model

- Publisher: **Qiusheng Wu / giswqs**, WHU Building Detection model.
- [Pinned model source](https://huggingface.co/giswqs/whu-building-unetplusplus-efficientnet-b4/tree/09df9efd323bbd3d56b98b4857129eb9b5baa2d3).
- License: **Apache License 2.0**. Full text: `licenses/Apache-2.0.txt`.
- Architecture: segmentation-models-pytorch UNet++ / EfficientNet-B4, two classes.
- Original artifact: `model.pth`, SHA-256 and exact revision in `models/manifest.json`.
- Modification: exported by RoofTrace to ONNX opset 17 with fixed RGB 512×512
  inputs. No fine-tuning or quantization. Conversion parity is recorded in the manifest.
- Hosted ONNX is a redistribution of this checkpoint, under Apache 2.0, and is
  excluded from the MIT source-code license.
- [Provider's training and inference implementation](https://github.com/opengeos/geoai):
  preprocessing verified against `geoai/timm_train.py` and `geoai/timm_segment.py`.
  Pixels are RGB floats divided by 255, without ImageNet mean/std normalization.

## WHU sample images and evaluation labels

- Dataset creators: **Shunping Ji, Shiqing Wei and Meng Lu**, Wuhan University.
- Citation: Ji, S., Wei, S., & Lu, M. (2019). *Fully Convolutional Networks for
  Multisource Building Identification*. IEEE Transactions on Geoscience and
  Remote Sensing, 57(1), 108–120. [DOI](https://doi.org/10.1109/TGRS.2018.2858815).
- [Hosted dataset release and license declaration](https://huggingface.co/datasets/giswqs/WHU-Building-Dataset).
- Exact revision: `c9ccc03ef4dd004b63cf179835771ab5e074bd3d`.
- The hosted release explicitly declares **CC BY 4.0**. See
  [the license](https://creativecommons.org/licenses/by/4.0/) and its
  [legal text](https://creativecommons.org/licenses/by/4.0/legalcode.en).
- Distributed unchanged RGB test images: `test_0002.png` → `courtyard.png`,
  `test_0006.png` → `neighborhood.png`, `test_0003.png` → `farmland.png`.
  All are 512×512 at the dataset's stated 0.3 m/pixel. Exact URLs and checksums
  are in `static/samples/manifest.json`. No masks are distributed with the app.
- These are inference demonstration images from the provider-declared **test**
  directory, distinct from its declared training split. RoofTrace performs no
  additional training. The publisher's split provenance has not been independently
  geographically audited. The samples overlap our six-tile diagnostic evaluation,
  so that diagnostic is not a blind evaluation of the demo selection.
- The [original WHU site](https://gpcv.whu.edu.cn/data/building_dataset.html)
  was inaccessible during implementation. Its research/non-commercial terms
  have been described in publications; the mirror's CC BY declaration should not
  be interpreted as an independent clearance for every future use. This public
  app is an educational research demonstration. Check the original provider's
  terms before commercial redistribution or replacing the samples at scale.
- Reference masks `test_0001`–`test_0006` are downloaded only by the optional
  evaluation script, into ignored `private/eval/`. They are never predictions.

## USGS transfer sample

- `phoenix.png`: **USDA / USGS The National Map: Orthoimagery**.
- [Source service](https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer).
- [USGS terms: data from The National Map is free and public domain](https://www.usgs.gov/faqs/are-there-any-costs-or-restrictions-usage-data-downloaded-national-map).
- Downloaded as a 512×512 RGB PNG from the service's export endpoint. Bounds,
  request URL and checksum are in `static/samples/manifest.json`.
- Requested sampling is 0.3 ground m/pixel, but this **does not increase native
  resolution**. The source service describes imagery typically at 1 m/pixel.
  Acquisition year for this chip has not been verified. No commercial basemap
  imagery or Google Maps imagery is included.
- This is an independent US location with no reference labels, included to expose
  transfer limitations. Do not infer accuracy on it from WHU test measurements.

## Dependencies and fonts

Direct runtime libraries: FastAPI (MIT), Uvicorn (BSD-3-Clause),
python-multipart (Apache-2.0), NumPy (BSD-3-Clause), Pillow (HPND),
ONNX Runtime (MIT) and OpenCV (Apache-2.0, wheel includes separate notices).
Export dependencies include PyTorch (BSD-style), torchvision (BSD-3-Clause),
segmentation-models-pytorch (MIT), timm (Apache-2.0) and ONNX (Apache-2.0).
Their packaged licenses apply; consult installed distribution metadata for
transitive notices. Dependencies are installed from their published packages.

DM Sans and Manrope are requested from Google Fonts under SIL Open Font License
1.1. System font fallbacks remain usable if that external request is blocked.

The proposal's SpaceNet 2 / fine-tuned YOLO approach was replaced with this
available building-specific segmentation checkpoint. **No SpaceNet data or
generic COCO detector is used in the final application.**
