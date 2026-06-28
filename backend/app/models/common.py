from __future__ import annotations

"""Shared domain models and enums."""

from datetime import time
from enum import Enum

from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    """Geographic coordinate validated to real-world bounds."""

    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)


class RequestUrgency(str, Enum):
    """Supported urgency levels for sample requests."""

    critical = "critical"
    high = "high"
    normal = "normal"


class VehicleType(str, Enum):
    """Courier vehicle types supported by the network."""

    motorcycle = "motorcycle"
    van = "van"


class RequestStatus(str, Enum):
    """Lifecycle states for a sample request."""

    open = "open"
    assigned = "assigned"
    failed = "failed"


class AllocationAlgorithm(str, Enum):
    """Supported allocation algorithms."""

    greedy = "greedy"
    hungarian = "hungarian"
    simulated_annealing = "simulated_annealing"


class TimeWindow(BaseModel):
    """Requested service window for a sample pickup."""

    start: time
    end: time


class AvailabilitySlot(BaseModel):
    """Courier availability window."""

    day: str
    start: time
    end: time
