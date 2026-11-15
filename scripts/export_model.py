"""Acquire the pinned Apache-2.0 checkpoint and export a CPU inference graph."""
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
import requests
import segmentation_models_pytorch as smp
import torch

ROOT = Path(__file__).resolve().parents[1]
REVISION = "09df9efd323bbd3d56b98b4857129eb9b5baa2d3"
REPO = "giswqs/whu-building-unetplusplus-efficientnet-b4"


def main():
    target = ROOT / "models"
    target.mkdir(exist_ok=True)
    weights = target / "model.pth"
    if not weights.exists():
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/model.pth"
        with requests.get(url, stream=True, timeout=180) as response:
            response.raise_for_status()
            with weights.open("wb") as file:
                for chunk in response.iter_content(1024 * 1024):
                    file.write(chunk)
    torch.set_num_threads(2)
    model = smp.UnetPlusPlus(encoder_name="efficientnet-b4", encoder_weights=None,
                            in_channels=3, classes=2).eval()
    state = torch.load(weights, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    dummy = torch.from_numpy(np.random.default_rng(42).random((1, 3, 512, 512), dtype=np.float32))
    destination = target / "rooftrace-whu.onnx"
    with torch.inference_mode():
        expected = model(dummy).numpy()
        torch.onnx.export(model, dummy, destination, input_names=["rgb"],
                          output_names=["logits"], opset_version=17, dynamo=False)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(destination), sess_options=options,
                                  providers=["CPUExecutionProvider"])
    actual = session.run(None, {"rgb": dummy.numpy()})[0]
    error = float(np.max(np.abs(actual - expected)))
    np.testing.assert_allclose(actual, expected, rtol=0.001, atol=0.0002)
    manifest = dict(model_id=REPO, revision=REVISION, license="Apache-2.0",
                    architecture="UNet++ / EfficientNet-B4", input_shape=[1, 3, 512, 512],
                    normalization="RGB float32 / 255, no mean/std normalization",
                    output="two-class logits: background=0, building=1",
                    checkpoint_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
                    onnx_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                    onnx_bytes=destination.stat().st_size, opset=17,
                    export_max_absolute_error=error)
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
