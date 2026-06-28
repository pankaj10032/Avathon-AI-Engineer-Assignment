from __future__ import annotations

"""Distance and travel-time utilities."""

from math import asin, cos, radians, sin, sqrt
from datetime import datetime
from typing import Any

TRAFFIC_MULTIPLIERS = {
    "rush_hour": 2.2,
    "daytime": 1.4,
    "night": 1.0,
}


def haversine_km(loc1: Any, loc2: Any) -> float:
    """Return the haversine distance in kilometers between two locations."""
    lat1 = loc1.lat if hasattr(loc1, "lat") else loc1["lat"]
    lng1 = loc1.lng if hasattr(loc1, "lng") else loc1["lng"]
    lat2 = loc2.lat if hasattr(loc2, "lat") else loc2["lat"]
    lng2 = loc2.lng if hasattr(loc2, "lng") else loc2["lng"]

    earth_radius_km = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)

    a = sin(d_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(d_lng / 2) ** 2
    c = 2 * asin(sqrt(a))
    return earth_radius_km * c


def traffic_multiplier(current_time: datetime) -> float:
    """Return the traffic multiplier for a given time of day."""
    hour = current_time.hour
    if hour in range(8, 10) or hour in range(17, 20):
        return TRAFFIC_MULTIPLIERS["rush_hour"]
    elif hour in range(10, 17):
        return TRAFFIC_MULTIPLIERS["daytime"]
    else:
        return TRAFFIC_MULTIPLIERS["night"]


def travel_time_minutes(loc1: Any, loc2: Any, speed_kmh: float, current_time: datetime) -> float:
    """Estimate traffic-adjusted travel time in minutes."""
    dist = haversine_km(loc1, loc2)
    adjusted_dist = dist * traffic_multiplier(current_time)
    return (adjusted_dist / speed_kmh) * 60 if speed_kmh > 0 else float("inf")
