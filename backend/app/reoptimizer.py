from __future__ import annotations

"""Urgent request re-optimization logic."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple

from app.algorithms.greedy import allocate_greedy
from app.algorithms.hungarian import allocate_hungarian
from app.algorithms.simulated_annealing import allocate_simulated_annealing
from app.models.assignment import Assignment
from app.models.common import AllocationAlgorithm, RequestUrgency
from app.models.courier import Courier
from app.models.sample_request import SampleRequest
from app.utils.distance import haversine_km, travel_time_minutes
from app.utils.scorer import score_assignment, explain_assignment

LOGGER = logging.getLogger(__name__)


def find_lowest_priority_assignment(current_assignments: List[Assignment], request_lookup: Dict[str, SampleRequest]) -> Assignment | None:
    """Return the least critical current assignment."""
    scored: list[tuple[int, float, Assignment]] = []
    for assignment in current_assignments:
        request = request_lookup.get(assignment.request_id)
        if not request:
            continue
        urgency_rank = {"normal": 0, "high": 1, "critical": 2}.get(request.urgency.value, 0)
        scored.append((urgency_rank, request.expiry_minutes, assignment))
    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], item[1], item[2].score))
    return scored[0][2]


def preempt_assignment(
    current_assignments: List[Assignment],
    preemptable: Assignment,
    new_request: SampleRequest,
    couriers: List[Courier],
    current_time: datetime,
) -> Tuple[List[Assignment], Dict[str, Any]]:
    """Preempt an existing assignment and reassign the freed courier."""
    courier_map = {courier.id: courier for courier in couriers}
    freed_courier = courier_map.get(preemptable.courier_id)
    if not freed_courier:
        return current_assignments, {"reoptimized": False, "reason": "courier_not_found"}

    updated_assignments = [assignment for assignment in current_assignments if assignment.request_id != preemptable.request_id]
    score_res = score_assignment(freed_courier, new_request, current_time)
    distance = haversine_km(freed_courier.location, new_request.location)

    new_assignment = Assignment(
        technician_id=freed_courier.id,
        request_id=new_request.id,
        score=round(score_res.total_score, 4),
        distance_km=round(distance, 2),
        algorithm_used=AllocationAlgorithm.greedy,
        eta_minutes=round(score_res.eta_minutes, 2),
        expiry_risk=score_res.expiry_risk_level in {"warning", "critical"},
        expiry_risk_level=score_res.expiry_risk_level,
        score_breakdown=score_res.breakdown,
        total_score=score_res.total_score,
        explanation=explain_assignment(score_res, freed_courier, new_request),
    )
    updated_assignments.append(new_assignment)
    return updated_assignments, {
        "reoptimized": True,
        "preempted_request": preemptable.request_id,
        "changed_assignment": {
            "technician_id": freed_courier.id,
            "from_request_id": preemptable.request_id,
            "to_request_id": new_request.id,
        },
    }


def handle_urgent_arrival(
    new_request: SampleRequest,
    current_assignments: List[Assignment],
    couriers: List[Courier],
    current_time: datetime,
    request_lookup: Dict[str, SampleRequest],
) -> Tuple[List[Assignment], Dict[str, Any]]:
    """Handle a new urgent request and preempt if beneficial."""
    LOGGER.info("urgent_request_received", extra={"request_id": new_request.id, "urgency": new_request.urgency.value})
    if new_request.urgency != RequestUrgency.critical:
        return current_assignments, {"reoptimized": False}

    preemptable = find_lowest_priority_assignment(current_assignments, request_lookup)
    if not preemptable:
        return current_assignments, {"reoptimized": False, "reason": "no_suitable_courier"}

    freed_courier = next((courier for courier in couriers if courier.id == preemptable.courier_id), None)
    if not freed_courier:
        return current_assignments, {"reoptimized": False, "reason": "no_suitable_courier"}

    new_cost = travel_time_minutes(freed_courier.location, new_request.location, freed_courier.speed_kmh, current_time)
    if new_cost < new_request.expiry_minutes * 0.7:
        LOGGER.info(
            "urgent_reoptimization_applied",
            extra={"request_id": new_request.id, "preempted_request": preemptable.request_id},
        )
        return preempt_assignment(current_assignments, preemptable, new_request, couriers, current_time)

    LOGGER.info("urgent_reoptimization_skipped", extra={"request_id": new_request.id, "reason": "no_suitable_courier"})
    return current_assignments, {"reoptimized": False, "reason": "no_suitable_courier"}
