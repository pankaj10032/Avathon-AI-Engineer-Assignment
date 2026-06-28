from __future__ import annotations

"""Step-by-step greedy allocation traces for animations."""

from datetime import datetime
from typing import Any, Dict, List

from app.algorithms.greedy import _compute_candidate_score
from app.models.repair_request import RepairRequest
from app.models.technician import Technician


def greedy_assignment_steps(
    couriers: List[Technician],
    requests: List[RepairRequest],
    current_time: datetime,
) -> List[Dict[str, Any]]:
    """Return ordered greedy allocation steps for frontend animation."""
    sorted_requests = sorted(
        requests,
        key=lambda r: (-r.priority, r.expiry_minutes, r.created_at, r.id),
    )
    working_loads = {courier.id: courier.active_samples_count for courier in couriers}
    steps: List[Dict[str, Any]] = []

    max_distance_km = 0.0
    for request in sorted_requests:
        for courier in couriers:
            candidate = _compute_candidate_score(courier, request, 1_000_000.0, current_time)
            if candidate is not None:
                max_distance_km = max(max_distance_km, candidate.distance_km)

    for request in sorted_requests:
        candidates = []
        for courier in couriers:
            candidate = _compute_candidate_score(courier, request, max_distance_km, current_time)
            if candidate is not None:
                candidates.append(candidate)
        candidates.sort(key=lambda c: (-c.score, c.distance_km, working_loads[c.technician.id], c.technician.id))
        winning = candidates[0] if candidates else None
        eligible = [
            {
                "courier_id": c.technician.id,
                "name": c.technician.name,
                "distance_km": c.distance_km,
                "eta_minutes": c.eta_minutes,
                "score": c.score,
            }
            for c in candidates
        ]
        steps.append(
            {
                "request": request.model_dump(),
                "eligible_couriers": eligible,
                "winning_courier": None if winning is None else {
                    "courier_id": winning.technician.id,
                    "name": winning.technician.name,
                    "distance_km": winning.distance_km,
                    "eta_minutes": winning.eta_minutes,
                    "score": winning.score,
                },
            }
        )
        if winning is not None:
            working_loads[winning.technician.id] += 1

    return steps
