"""Download the immutable RoofTrace ONNX release; verify SHA-256 before use."""
import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/jessesuniljs1-collab/rooftrace-geoai/releases/download/model-v1/rooftrace-whu.onnx"


def main():
    manifest = json.loads((ROOT / "models" / "manifest.json").read_text())
    path = Path(os.environ.get("ROOFTRACE_MODEL_PATH", ROOT / "models" / "rooftrace-whu.onnx"))
    path.parent.mkdir(parents=True, exist_ok=True)
    expected = manifest["onnx_sha256"]
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
        print("Model already present; SHA-256 verified.")
        return
    temporary = path.with_suffix(".download")
    try:
        request = urllib.request.Request(URL, headers={"User-Agent": "RoofTrace-model-setup/1.0"})
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Model checksum mismatch; refusing to install.")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    print("Model acquired and SHA-256 verified.")


if __name__ == "__main__":
    main()
