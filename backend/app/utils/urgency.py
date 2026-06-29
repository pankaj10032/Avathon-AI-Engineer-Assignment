from __future__ import annotations

"""Request urgency scoring helpers."""

from datetime import datetime, timedelta, timezone
from typing import Any


def _current_time_to_utc(current_time: datetime) -> datetime:
    """Normalize datetimes to UTC for comparison."""
    if current_time.tzinfo is None:
        return current_time.replace(tzinfo=timezone.utc)
    return current_time.astimezone(timezone.utc)


def compute_urgency_score(request: Any, current_time: datetime) -> float:
    """Compute a decaying urgency score from 1.0 to 0.0."""
    current_time = _current_time_to_utc(current_time)
    created_at = _current_time_to_utc(request.created_at)
    elapsed = max(0.0, (current_time - created_at).total_seconds() / 60.0)
    decay_rate = 3.0 if request.urgency == "critical" else 1.0
    if request.expiry_minutes <= 0:
        return 0.0
    score = max(0.0, 1 - (elapsed / request.expiry_minutes) * decay_rate)
    return score


def flag_expiry_risk(request: Any, eta_minutes: float, current_time: datetime) -> bool:
    """Return True when estimated arrival exceeds the expiry window."""
    current_time = _current_time_to_utc(current_time)
    created_at = _current_time_to_utc(request.created_at)
    eta_arrival = current_time + timedelta(minutes=float(eta_minutes))
    elapsed_at_eta = max(0.0, (eta_arrival - created_at).total_seconds() / 60.0)
    return elapsed_at_eta > 0.8 * request.expiry_minutes
