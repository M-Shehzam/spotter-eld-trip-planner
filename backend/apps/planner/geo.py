"""Distance helpers.

Two formulas, each chosen for a reason.

``haversine_miles`` is exact over any separation and measures the route
itself, where small errors would accumulate over thousands of vertices.

``planar_miles`` is an equirectangular approximation. Within the hundred-mile
window used to name the nearest town it is accurate to a fraction of a mile,
and it costs one cosine against haversine's several trigonometric calls.

Ported from the routing helpers in spotter-fuel-route-api.
"""

from __future__ import annotations

import numpy as np

EARTH_RADIUS_MILES = 3958.7613


def haversine_miles(
    lat1: np.ndarray | float,
    lon1: np.ndarray | float,
    lat2: np.ndarray | float,
    lon2: np.ndarray | float,
) -> np.ndarray:
    """Great-circle distance in miles. Broadcasts like any NumPy operation."""
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = phi2 - phi1
    delta_lambda = np.radians(np.asarray(lon2) - np.asarray(lon1))

    a = (
        np.sin(delta_phi / 2.0) ** 2
        + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def planar_miles(
    lat1: np.ndarray | float,
    lon1: np.ndarray | float,
    lat2: np.ndarray | float,
    lon2: np.ndarray | float,
    cos_reference_latitude: float,
) -> np.ndarray:
    """Equirectangular distance in miles, for short separations only.

    Args:
        cos_reference_latitude: Cosine of a latitude representative of the
            comparison, supplied once per block to keep the cosine out of the
            inner loop.
    """
    y = np.radians(np.asarray(lat2) - lat1)
    x = np.radians(np.asarray(lon2) - lon1) * cos_reference_latitude
    return EARTH_RADIUS_MILES * np.sqrt(x * x + y * y)


def cumulative_miles(latitudes: np.ndarray, longitudes: np.ndarray) -> np.ndarray:
    """Distance travelled along a polyline, one entry per vertex, starting at 0."""
    if latitudes.size < 2:
        return np.zeros_like(latitudes)

    steps = haversine_miles(
        latitudes[:-1], longitudes[:-1], latitudes[1:], longitudes[1:]
    )
    out = np.empty(latitudes.size, dtype=np.float64)
    out[0] = 0.0
    np.cumsum(steps, out=out[1:])
    return out
