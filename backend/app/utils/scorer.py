from __future__ import annotations

"""Domain-aware assignment scoring for all allocation algorithms."""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Dict

from app.config import (
    MAX_COURIER_SPEED_KMH,
    MAX_MOTORCYCLE_SAMPLES,
    MAX_REASONABLE_DISTANCE_KM,
    MAX_VAN_SAMPLES,
    SCORE_CAPACITY_WEIGHT,
    SCORE_DISTANCE_WEIGHT,
    SCORE_ETA_WEIGHT,
    SCORE_EXPIRY_RISK_WEIGHT,
    SCORE_SPEED_WEIGHT,
)
from app.models.common import VehicleType
from app.utils.distance import haversine_km, travel_time_minutes


@dataclass(frozen=True)
class AssignmentScore:
    """Structured scoring result for one courier-request candidate."""

    is_feasible: bool
    total_score: float
    eta_minutes: float
    expiry_risk_level: str
    capacity_ok: bool
    breakdown: Dict[str, float]


def _max_capacity(vehicle_type: VehicleType) -> int:
    """Return the maximum load for a given vehicle type."""
    return MAX_MOTORCYCLE_SAMPLES if vehicle_type == VehicleType.motorcycle else MAX_VAN_SAMPLES


def _within_shift(courier: Any, request: Any) -> bool:
    """Check whether a request window overlaps the courier shift."""
    request_start = request.time_window.start
    request_end = request.time_window.end
    shift_start = courier.shift_start
    shift_end = courier.shift_end
    return not (request_end <= shift_start or request_start >= shift_end)


def score_assignment(courier: Any, request: Any, current_time: datetime, config: Any | None = None) -> AssignmentScore:
    """Score a courier-request pairing using domain-aware factors."""
    weights = config or {}
    distance_weight = float(weights.get("distance", SCORE_DISTANCE_WEIGHT))
    speed_weight = float(weights.get("speed", SCORE_SPEED_WEIGHT))
    capacity_weight = float(weights.get("capacity", SCORE_CAPACITY_WEIGHT))
    eta_weight = float(weights.get("eta", SCORE_ETA_WEIGHT))
    expiry_weight = float(weights.get("expiry_risk", SCORE_EXPIRY_RISK_WEIGHT))

    max_capacity = _max_capacity(courier.vehicle_type)
    capacity_ok = courier.active_samples_count < max_capacity
    organ_ok = request.sample_type != "organ" or courier.vehicle_type == VehicleType.van
    shift_ok = _within_shift(courier, request)

    eta_minutes = travel_time_minutes(courier.location, request.location, courier.speed_kmh, current_time)
    if request.expiry_minutes <= 0:
        return AssignmentScore(
            is_feasible=False,
            total_score=0.0,
            eta_minutes=float(eta_minutes),
            expiry_risk_level="impossible",
            capacity_ok=capacity_ok,
            breakdown={"distance_km": 0.0, "distance": 0.0, "speed": 0.0, "capacity": 0.0, "eta": 0.0, "expiry_risk": 0.0},
        )

    from datetime import timezone
    current_time_utc = current_time.astimezone(timezone.utc) if current_time.tzinfo else current_time.replace(tzinfo=timezone.utc)
    created_at_utc = request.created_at.astimezone(timezone.utc) if request.created_at.tzinfo else request.created_at.replace(tzinfo=timezone.utc)
    elapsed_minutes = (current_time_utc - created_at_utc).total_seconds() / 60.0
    remaining_minutes = request.expiry_minutes - elapsed_minutes

    feasible = capacity_ok and organ_ok and shift_ok and remaining_minutes > 0 and eta_minutes < remaining_minutes
    distance_km = haversine_km(courier.location, request.location)
    buffer_minutes = remaining_minutes - eta_minutes
    buffer_fraction = buffer_minutes / request.expiry_minutes if request.expiry_minutes > 0 else 0.0

    if not feasible or remaining_minutes <= 0 or buffer_fraction <= 0:
        expiry_risk_level = "impossible"
        expiry_score = 0.0
    elif buffer_fraction >= 0.5:
        expiry_risk_level = "safe"
        expiry_score = 1.0
    elif buffer_fraction >= 0.25:
        expiry_risk_level = "warning"
        expiry_score = 0.6
    else:
        expiry_risk_level = "critical"
        expiry_score = 0.2

    distance_score = max(0.0, 1.0 - (distance_km / MAX_REASONABLE_DISTANCE_KM))
    speed_score = min(1.0, courier.speed_kmh / MAX_COURIER_SPEED_KMH)
    capacity_score = (max_capacity - courier.active_samples_count) / max_capacity
    eta_score = max(0.0, 1.0 - (eta_minutes / request.expiry_minutes))

    total_score = (
        distance_score * distance_weight
        + speed_score * speed_weight
        + capacity_score * capacity_weight
        + eta_score * eta_weight
        + expiry_score * expiry_weight
    )

    breakdown = {
        "distance_km": round(distance_km, 2),
        "distance": round(distance_score, 4),
        "speed": round(speed_score, 4),
        "capacity": round(capacity_score, 4),
        "eta": round(eta_score, 4),
        "expiry_risk": round(expiry_score, 4),
    }

    return AssignmentScore(
        is_feasible=feasible,
        total_score=round(max(0.0, min(1.0, total_score)), 4) if feasible else 0.0,
        eta_minutes=round(eta_minutes, 2),
        expiry_risk_level=expiry_risk_level,
        capacity_ok=capacity_ok,
        breakdown=breakdown,
    )


def explain_assignment(score: AssignmentScore, courier: Any, request: Any) -> str:
    """Generate a plain-English explanation for an assignment."""
    parts = []
    parts.append(f"{courier.name} ({courier.vehicle_type.value})")
    parts.append(f"ETA {score.eta_minutes:.1f}min")
    parts.append(f"{score.expiry_risk_level.upper()} expiry risk")
    parts.append(f"{score.breakdown['distance_km']:.1f}km away")
    if score.breakdown["capacity"] > 0.8:
        parts.append("low workload")
    return " | ".join(parts)
