"""Great-circle distance on a sphere; no external geocoding service required."""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    # Clamp floating-point round-off at antipodal points.
    return 2 * EARTH_RADIUS_KM * asin(sqrt(min(1.0, max(0.0, a))))
