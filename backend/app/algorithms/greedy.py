from __future__ import annotations

"""Greedy allocation strategy."""

import logging
import time as time_module
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Sequence, Tuple

from app.models.assignment import Assignment
from app.models.common import AllocationAlgorithm, AvailabilitySlot, TimeWindow
from app.config import AVAILABILITY_WEIGHT, DISTANCE_WEIGHT, WORKLOAD_WEIGHT
from app.models.repair_request import RepairRequest
from app.models.technician import Technician
from app.utils.distance import haversine_km, travel_time_minutes
from app.utils.scorer import AssignmentScore, explain_assignment, score_assignment

LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True)
class _CandidateScore:
    technician: Technician
    score: float
    cost: float
    distance_km: float
    eta_minutes: float
    skill_match: float
    workload_score: float
    availability_score: float
    urgency_score: float
    expiry_risk: bool
    expiry_risk_level: str
    breakdown: dict[str, float]


def _time_to_minutes(value: time) -> int:
    """Convert a time value to minutes since midnight."""
    return value.hour * 60 + value.minute


def _overlap_minutes(a_start: time, a_end: time, b_start: time, b_end: time) -> int:
    """Compute overlapping minutes between two time windows."""
    start = max(_time_to_minutes(a_start), _time_to_minutes(b_start))
    end = min(_time_to_minutes(a_end), _time_to_minutes(b_end))
    return max(0, end - start)


def _availability_overlap_score(schedule: Sequence[AvailabilitySlot], request_window: TimeWindow) -> float:
    """Score the overlap between a courier schedule and a request window."""
    if not schedule:
        return 0.0

    request_minutes = max(1, _time_to_minutes(request_window.end) - _time_to_minutes(request_window.start))
    best_overlap = 0

    for slot in schedule:
        overlap = _overlap_minutes(slot.start, slot.end, request_window.start, request_window.end)
        best_overlap = max(best_overlap, overlap)

    return min(1.0, best_overlap / request_minutes)


def _normalize_distance(distance_km: float, max_distance_km: float) -> float:
    """Normalize distance so closer couriers score higher."""
    if max_distance_km <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - (distance_km / max_distance_km)))


def _compute_candidate_score(
    technician: Technician,
    request: RepairRequest,
    max_distance_km: float,
    current_time: datetime,
    config: dict[str, float] | None = None,
) -> _CandidateScore | None:
    """Compute a candidate score if a technician satisfies hard constraints."""
    score = score_assignment(technician, request, current_time, config)
    if not score.is_feasible:
        return None

    distance_km = haversine_km(technician.location, request.location)
    availability_score = _availability_overlap_score(technician.availability_schedule, request.time_window)
    eta_minutes = score.eta_minutes
    workload_score = score.breakdown["capacity"]
    distance_score = score.breakdown["distance"]
    urgency_score = score.breakdown["eta"]
    expiry_risk = score.expiry_risk_level in {"warning", "critical", "impossible"}
    skill_match = 1.0
    cost = 1.0 - score.total_score

    return _CandidateScore(
        technician=technician,
        score=round(score.total_score, 4),
        cost=round(cost, 4),
        distance_km=round(distance_km, 2),
        eta_minutes=round(eta_minutes, 2),
        skill_match=skill_match,
        workload_score=round(workload_score, 4),
        availability_score=round(availability_score, 4),
        urgency_score=round(urgency_score, 4),
        expiry_risk=expiry_risk,
        expiry_risk_level=score.expiry_risk_level,
        breakdown=score.breakdown,
    )


def _assignment_explanation(candidate: _CandidateScore) -> str:
    """Create a human-readable explanation for a greedy assignment."""
    dummy = AssignmentScore(
        is_feasible=True,
        total_score=candidate.score,
        eta_minutes=candidate.eta_minutes,
        expiry_risk_level=candidate.expiry_risk_level,
        capacity_ok=True,
        breakdown=candidate.breakdown,
    )
    return explain_assignment(dummy, candidate.technician, None)


def allocate_greedy(
    technicians: List[Technician],
    requests: List[RepairRequest],
    current_time: datetime,
    config: dict[str, float] | None = None,
) -> Tuple[List[Assignment], List[RepairRequest], Dict[str, Any]]:
    """
    Greedy allocation:
    - Sort requests by priority descending, then earliest time window start.
    - For each request, pick the highest-scoring technician that satisfies hard constraints.
    """
    start_time = time_module.perf_counter()
    LOGGER.info("greedy_allocation_started", extra={"requests": len(requests), "technicians": len(technicians)})
    sorted_requests = sorted(
        requests,
        key=lambda r: (-r.priority, r.time_window.start.hour, r.time_window.start.minute, r.id),
    )

    assignments: List[Assignment] = []
    unassigned: List[RepairRequest] = []
    working_loads = {tech.id: tech.current_load for tech in technicians}

    max_distance_km = 0.0
    for request in sorted_requests:
        for tech in technicians:
            distance = haversine_km(tech.location, request.location)
            max_distance_km = max(max_distance_km, distance)

    total_requests = len(sorted_requests)
    assigned_count = 0
    total_score = 0.0
    total_distance = 0.0

    for request in sorted_requests:
        candidates: List[_CandidateScore] = []
        for tech in technicians:
            candidate = _compute_candidate_score(tech, request, max_distance_km, current_time, config)
            if candidate is not None:
                candidates.append(candidate)

        if not candidates:
            unassigned.append(request)
            continue

        candidates.sort(
            key=lambda c: (
                -c.score,
                c.distance_km,
                working_loads[c.technician.id],
                c.technician.id,
            )
        )
        best = candidates[0]

        assignment = Assignment(
            technician_id=best.technician.id,
            request_id=request.id,
            score=best.score,
            distance_km=best.distance_km,
            algorithm_used=AllocationAlgorithm.greedy,
            eta_minutes=best.eta_minutes,
            expiry_risk=best.expiry_risk,
            expiry_risk_level=best.expiry_risk_level,
            score_breakdown=best.breakdown,
            total_score=best.score,
            explanation=_assignment_explanation(best),
        )
        assignments.append(assignment)
        LOGGER.info(
            "assignment_decision",
            extra={
                "courier_id": best.technician.id,
                "request_id": request.id,
                "score": best.score,
                "reason": "highest_greedy_score",
            },
        )
        assigned_count += 1
        total_score += best.score
        total_distance += best.distance_km
        working_loads[best.technician.id] += 1

    utilizations = []
    for tech in technicians:
        final_load = working_loads[tech.id]
        utilizations.append((final_load - tech.current_load) / final_load if final_load > 0 else 0.0)

    runtime_ms = round((time_module.perf_counter() - start_time) * 1000.0, 2)
    LOGGER.info("greedy_allocation_finished", extra={"runtime_ms": runtime_ms, "assigned": assigned_count})

    metrics: Dict[str, Any] = {
        "algorithm": AllocationAlgorithm.greedy.value,
        "total_assigned": assigned_count,
        "total_unassigned": len(unassigned),
        "avg_distance_km": round(total_distance / assigned_count, 2) if assigned_count else 0.0,
        "max_distance_km": round(max((a.distance_km for a in assignments), default=0.0), 2),
        "avg_technician_utilization": round(sum(utilizations) / len(utilizations), 4) if utilizations else 0.0,
        "total_cost_score": round(sum(1.0 - a.score for a in assignments), 4),
        "pct_expiry_risk": round(
            sum(1 for a in assignments if a.expiry_risk) / len(assignments), 4
        )
        if assignments
        else 0.0,
        "runtime_ms": runtime_ms,
    }

    return assignments, unassigned, metrics
