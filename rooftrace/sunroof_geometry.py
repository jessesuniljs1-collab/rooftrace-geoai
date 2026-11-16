"""Geometry adapted from AKASH2907/project_sunroof_india (Apache-2.0).

Upstream commit: 0c6426b9c06aa784cfee2860d3a9965c36d9222e.
Sources: Google Map to Pixels/lat_long_metre_pixel.py; Solar Panel Placement/panels_atlast.py.
Modified by team 404: JCT Not Found, 2026: pure functions, explicit units,
validation, image-scale handling and vectorized rotation. See third-party notices.
"""
import math

import numpy as np


def meters_per_pixel(latitude: float, zoom: int, image_scale: int = 1) -> float:
    """Web Mercator ground scale. Only valid for an unresized, north-up map image."""
    if not -85 <= latitude <= 85 or not 0 <= zoom <= 23 or image_scale not in (1, 2):
        raise ValueError("Invalid Web Mercator latitude, zoom or image scale.")
    return math.cos(math.radians(latitude)) * (2 * math.pi * 6378137) / (256 * 2 ** zoom * image_scale)


def rotate_points(points, angle_degrees, center=(0, 0)):
    """Rotate 2D points around a center. Adapted from upstream rotation()."""
    angle = math.radians(angle_degrees)
    matrix = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    points = np.asarray(points, dtype=float)
    return (points - center) @ matrix.T + center
