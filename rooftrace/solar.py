"""Free, transparent flat-roof solar scenarios from real segmentation masks.

Panel fit is 2D geometry, not measured suitability. PVGIS supplies regional yield.
No Google imagery is fetched, retained, traced or used to train a model.
"""
import calendar
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import cv2
import numpy as np
from pydantic import BaseModel, Field

from rooftrace.inference import MIN_AREA, regions_from_probability
from rooftrace.sunroof_geometry import rotate_points

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
_weather_cache = {}
_weather_lock = threading.Lock()


class SolarSettings(BaseModel):
    meters_per_pixel: float = Field(ge=0.05, le=5)
    latitude: float = Field(ge=-60, le=70)
    longitude: float = Field(ge=-180, le=180)
    tilt_degrees: float = Field(default=10, ge=0, le=60)
    azimuth_degrees: float = Field(default=180, ge=0, le=360)
    panel_watts: int = Field(default=450, ge=100, le=750)
    panel_length_m: float = Field(default=2, ge=1, le=3)
    panel_width_m: float = Field(default=1.1, ge=0.5, le=2)
    setback_m: float = Field(default=0.5, ge=0, le=2)
    panel_gap_m: float = Field(default=0.1, ge=0, le=1)
    usable_fraction: float = Field(default=0.6, ge=0.1, le=1)
    system_loss_percent: float = Field(default=14, ge=0, le=50)
    additional_shade_percent: float = Field(default=0, ge=0, le=80)
    excluded_region_ids: list[int] = Field(default_factory=list, max_length=200)


def get_pvgis(settings: SolarSettings):
    """One real 1 kWp simulation per weather scenario, reused across roofs.

    Coordinates are rounded to 0.01 degrees for coarse regional climate data.
    Cache is bounded, in memory, 24 hours, and contains no images or API secrets.
    """
    key = (round(settings.latitude, 2), round(settings.longitude, 2),
           round(settings.tilt_degrees, 1), round(settings.azimuth_degrees, 1),
           round(settings.system_loss_percent, 1))
    with _weather_lock:
        item = _weather_cache.get(key)
        if item and time.time() - item[0] < 86400:
            return item[1]
    lat, lon, tilt, azimuth, loss = key
    params = dict(lat=lat, lon=lon, peakpower=1, loss=loss, outputformat="json",
                  pvtechchoice="crystSi", mountingplace="free", angle=tilt,
                  aspect=azimuth - 180, raddatabase="PVGIS-ERA5", usehorizon=1)
    url = PVGIS_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "RoofTrace-Solar-research/2.0"})
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            data = json.loads(response.read(200_000))
        output = data["outputs"]
        monthly = output["monthly"]["fixed"]
        annual = float(output["totals"]["fixed"]["E_y"])
        if len(monthly) != 12 or not math.isfinite(annual) or not 0 < annual < 4000:
            raise ValueError("Invalid solar resource response")
        meteo = data["inputs"]["meteo_data"]
        result = dict(provider="European Commission JRC PVGIS 5.3", database=meteo["radiation_db"],
                      years=[meteo["year_min"], meteo["year_max"]], url=url,
                      annual_kwh_per_kwp=annual,
                      monthly_kwh_per_kwp=[round(float(m["E_m"]), 3) for m in monthly],
                      monthly_irradiation_kwh_m2=[round(float(m["H(i)_m"]), 3) for m in monthly],
                      latitude=lat, longitude=lon, source="live PVGIS API calculation",
                      fetched_unix=int(time.time()),
                      limitation="Regional climate and terrain horizon; nearby trees, buildings, roof structure and local shade are not measured.")
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError, TypeError) as error:
        raise RuntimeError("PVGIS solar weather data is unavailable for this location right now. Try again, or choose another location. No energy estimate has been invented.") from error
    with _weather_lock:
        if len(_weather_cache) >= 128:
            _weather_cache.pop(next(iter(_weather_cache)))
        _weather_cache[key] = (time.time(), result)
    return result


def fit_panels(mask: np.ndarray, settings: SolarSettings, origin):
    """Conservative discrete grid search at 0, 30, 60 and 90 degrees.

    Search four offsets per angle. Every covered output pixel must be inside the
    eroded roof mask. No panel is a model detection or an optimized engineering plan.
    """
    scale = settings.meters_per_pixel
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    allowed = (distance > settings.setback_m / scale + 0.5).astype(np.uint8)
    max_panels = math.floor(int(mask.sum()) * scale * scale * settings.usable_fraction /
                            (settings.panel_length_m * settings.panel_width_m))
    if max_panels <= 0 or not np.any(allowed):
        return [], int(allowed.sum())
    length = max(1, math.ceil(settings.panel_length_m / scale))
    width = max(1, math.ceil(settings.panel_width_m / scale))
    gap = math.ceil(settings.panel_gap_m / scale)
    h, w = mask.shape
    side = int(math.ceil(math.hypot(h, w))) + 4
    center = np.array([w / 2, h / 2])
    pad_center = np.array([side / 2, side / 2])
    best = []
    for angle in [0, 30, 60, 90]:
        matrix = cv2.getRotationMatrix2D(tuple(center), angle, 1)
        matrix[:, 2] += pad_center - center
        rotated = cv2.warpAffine(allowed, matrix, (side, side), flags=cv2.INTER_NEAREST)
        integral = cv2.integral(rotated)
        inverse = cv2.invertAffineTransform(matrix)
        step_x, step_y = length + gap, width + gap
        for ox, oy in [(0, 0), (step_x // 2, 0), (0, step_y // 2), (step_x // 2, step_y // 2)]:
            xs = np.arange(ox, side - length + 1, step_x)
            ys = np.arange(oy, side - width + 1, step_y)
            if not len(xs) or not len(ys):
                continue
            xx, yy = np.meshgrid(xs, ys)
            sums = (integral[yy + width, xx + length] - integral[yy, xx + length]
                    - integral[yy + width, xx] + integral[yy, xx])
            candidates = np.argwhere(sums == width * length)
            panels = []
            for row, col in candidates[:3000]:
                x, y = int(xs[col]), int(ys[row])
                corners = np.array([[x, y], [x + length, y], [x + length, y + width], [x, y + width]], dtype=float)
                # Use the attributed upstream rotation helper; match OpenCV inverse.
                points = rotate_points(corners, angle, pad_center) + center - pad_center
                expected = cv2.transform(corners[None], inverse)[0]
                if not np.allclose(points, expected, atol=1e-5):
                    raise RuntimeError("Panel coordinate transform failed")
                integer = np.rint(points).astype(np.int32)
                if np.any(integer[:, 0] < 0) or np.any(integer[:, 0] >= w) or np.any(integer[:, 1] < 0) or np.any(integer[:, 1] >= h):
                    continue
                bx, by, bw, bh = cv2.boundingRect(integer)
                patch = np.zeros((bh, bw), dtype=np.uint8)
                cv2.fillConvexPoly(patch, integer - [bx, by], 1)
                if np.any((patch > 0) & (allowed[by:by + bh, bx:bx + bw] == 0)):
                    continue
                panels.append([[round(float(px + origin[0]), 2), round(float(py + origin[1]), 2)] for px, py in points])
                if len(panels) >= min(max_panels, 2000):
                    break
            if len(panels) > len(best):
                best = panels
    return best, int(allowed.sum())


def analyze_solar(probability: np.ndarray, threshold: float, settings: SolarSettings, weather=None):
    regions = regions_from_probability(probability, threshold)
    if len(regions) > 200:
        raise ValueError("Solar planning supports up to 200 roof regions per scene. Crop a smaller area first.")
    mask = (probability.astype(np.float32) / 255 >= threshold).astype(np.uint8)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    # Label and displayed region IDs use the same scan and minimum-area rule.
    labels_kept = [i for i in range(1, len(stats)) if stats[i, cv2.CC_STAT_AREA] >= MIN_AREA]
    roofs = []
    total_panels = 0
    for region, label in zip(regions, labels_kept, strict=True):
        x, y, xmax, ymax = (region[k] for k in ["x_min", "y_min", "x_max", "y_max"])
        local_mask = np.pad((labels[y:ymax, x:xmax] == label).astype(np.uint8), 1)
        excluded = region["id"] in settings.excluded_region_ids
        panels, available = ([], 0) if excluded else fit_panels(local_mask, settings, (x - 1, y - 1))
        total_panels += len(panels)
        if total_panels > 5000:
            raise ValueError("This scene produces more than 5,000 illustrative panels. Use a smaller crop.")
        capacity = len(panels) * settings.panel_watts / 1000
        roofs.append(dict(**region, excluded=excluded, footprint_m2=round(region["area_pixels"] * settings.meters_per_pixel ** 2, 2),
                          setback_available_m2=round(available * settings.meters_per_pixel ** 2, 2), panel_count=len(panels),
                          capacity_kwp=round(capacity, 3), panels=panels))
    # Avoid a network request for a zero-capacity result.
    weather = weather or (get_pvgis(settings) if total_panels else None)
    shade = 1 - settings.additional_shade_percent / 100
    for roof in roofs:
        roof["annual_kwh"] = round(roof["capacity_kwp"] * weather["annual_kwh_per_kwp"] * shade, 1) if weather else 0
        roof["monthly_kwh"] = [round(roof["capacity_kwp"] * energy * shade, 1) for energy in weather["monthly_kwh_per_kwp"]] if weather else [0] * 12
    return dict(method="RoofTrace flat-roof screening v2", threshold=threshold, settings=settings.model_dump(),
                roof_count=len(roofs), included_roof_count=sum(not r["excluded"] for r in roofs), roofs=roofs,
                panel_count=total_panels, capacity_kwp=round(sum(r["capacity_kwp"] for r in roofs), 3),
                annual_kwh=round(sum(r["annual_kwh"] for r in roofs), 1),
                monthly_kwh=[round(sum(r["monthly_kwh"][i] for r in roofs), 1) for i in range(12)],
                months=[calendar.month_abbr[i] for i in range(1, 13)], weather=weather,
                limitation="Screening scenario, not a design or a measured roof suitability assessment. Segmentation can merge homes. Flat-roof 2D layouts do not measure pitch, obstacles, load bearing, setbacks required by local code, nearby shade or grid connection.")
