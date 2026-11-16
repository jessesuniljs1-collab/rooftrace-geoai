"""Single-service FastAPI application. Uploads and results stay request-local."""
import json
import logging

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rooftrace.inference import (INFERENCE_GATE, MAX_BYTES, MODEL_ID, ROOT,
                                decode_image, decode_probability, encode_probability,
                                predict, regions_from_probability)
from rooftrace.solar import SolarSettings, analyze_solar

app = FastAPI(title="RoofTrace Solar", version="2.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
SAMPLES = json.loads((ROOT / "static" / "samples" / "manifest.json").read_text())
logger = logging.getLogger("rooftrace")


@app.middleware("http")
async def bound_request(request: Request, call_next):
    if request.method == "POST":
        maximum = MAX_BYTES + 65_536
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "Invalid content length."}, status_code=400)
        oversized = length > maximum
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            # Drain a bounded rejected body so upload clients can finish writing
            # before the 413 response. Never retain rejected content.
            if size > 4_500_000:
                return JSONResponse({"detail": "Request exceeds the 3.5 MB upload limit."}, status_code=413)
            if size > maximum:
                oversized = True
            if oversized:
                chunks.clear()
            else:
                chunks.append(chunk)
        if oversized:
            return JSONResponse({"detail": "Request exceeds the 3.5 MB upload limit."}, status_code=413)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/health")
def health():
    path = ROOT / "models" / "rooftrace-whu.onnx"
    available = path.is_file()
    return JSONResponse({"status": "ok" if available else "model_missing", "model": MODEL_ID,
                         "runtime": "ONNX Runtime CPU", "version": "2.0.0", "solar": "PVGIS 5.3, no API key"}, status_code=200 if available else 503)


@app.get("/api/samples")
def samples():
    return SAMPLES


@app.post("/api/analyze")
def analyze(file: UploadFile | None = File(None), sample_id: str | None = Form(None),
            threshold: float = Form(0.5)):
    if bool(file) == bool(sample_id):
        raise HTTPException(422, "Choose exactly one image: upload or sample.")
    if not 0.1 <= threshold <= 0.9:
        raise HTTPException(422, "Probability threshold must be between 0.10 and 0.90.")
    try:
        if sample_id:
            sample = next((s for s in SAMPLES if s["id"] == sample_id), None)
            if sample is None:
                raise HTTPException(404, "Sample not found.")
            data = (ROOT / "static" / "samples" / f"{sample_id}.png").read_bytes()
            identifier = sample_id
        else:
            if file.content_type not in {"image/jpeg", "image/png", "application/octet-stream"}:
                raise ValueError("Please upload a JPG or PNG image.")
            data = file.file.read(MAX_BYTES + 1)
            # Original filename is never used in a path, log, or spreadsheet cell.
            identifier = "upload"
        image = decode_image(data)
        if not INFERENCE_GATE.acquire(timeout=1):
            raise HTTPException(503, "The model is busy. Please try again in a moment.")
        try:
            probability, timing = predict(image)
        finally:
            INFERENCE_GATE.release()
        regions = regions_from_probability(probability, threshold)
        return {"image_id": identifier, "width": image.width, "height": image.height,
                "model": MODEL_ID, "threshold": threshold, "count": len(regions),
                "regions": regions, "probability_png": encode_probability(probability), **timing}
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.error("Inference failed (%s)", type(error).__name__)
        raise HTTPException(503, "Inference could not finish. Please retry or use a smaller image.") from error
    finally:
        if file:
            file.file.close()


class RegionRequest(BaseModel):
    probability_png: str = Field(max_length=3_400_000)
    threshold: float = Field(ge=0.1, le=0.9)


@app.post("/api/regions")
def filter_regions(body: RegionRequest):
    try:
        regions = regions_from_probability(decode_probability(body.probability_png), body.threshold)
        return {"regions": regions, "count": len(regions), "threshold": body.threshold}
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


class SolarRequest(RegionRequest):
    settings: SolarSettings


@app.post("/api/solar")
def solar_potential(body: SolarRequest):
    if not INFERENCE_GATE.acquire(timeout=1):
        raise HTTPException(503, "Analysis is busy. Please try again in a moment.")
    try:
        probability = decode_probability(body.probability_png)
        return analyze_solar(probability, body.threshold, body.settings)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error
    except Exception as error:
        logger.error("Solar analysis failed (%s)", type(error).__name__)
        raise HTTPException(503, "Solar analysis could not finish. Try a smaller crop or another location.") from error
    finally:
        INFERENCE_GATE.release()
