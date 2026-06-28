from __future__ import annotations

"""Hybrid dispatcher combining greedy, Hungarian, and SA strategies."""

from copy import deepcopy
from datetime import datetime
import logging
from typing import Any, Dict, List, Tuple

from app.algorithms.greedy import allocate_greedy
from app.algorithms.hungarian import allocate_hungarian
from app.algorithms.simulated_annealing import allocate_simulated_annealing
from app.models.assignment import Assignment
from app.models.common import AllocationAlgorithm, RequestUrgency
from app.models.repair_request import RepairRequest
from app.models.technician import Technician

LOGGER = logging.getLogger(__name__)


def _clone_couriers(couriers: List[Technician]) -> List[Technician]:
    """Clone couriers so downstream algorithms do not mutate shared state."""
    return [deepcopy(courier) for courier in couriers]


def _update_availability(couriers: List[Technician], assignments: List[Assignment]) -> List[Technician]:
    """Increase courier load after applying assignments."""
    courier_map = {courier.id: courier for courier in _clone_couriers(couriers)}
    for assignment in assignments:
        if assignment.courier_id in courier_map:
            courier = courier_map[assignment.courier_id]
            courier_map[assignment.courier_id] = courier.model_copy(
                update={"active_samples_count": courier.active_samples_count + 1}
            )
    return list(courier_map.values())


def _combine_metrics(
    assignments: List[Assignment],
    algorithms_used: List[str],
    runtime_ms: float,
) -> Dict[str, Any]:
    """Combine metrics from the hybrid allocation workflow."""
    if assignments:
        avg_distance_km = round(sum(a.distance_km for a in assignments) / len(assignments), 2)
        max_distance_km = round(max(a.distance_km for a in assignments), 2)
        avg_utilization = 0.0
        total_cost_score = round(sum(1.0 - a.score for a in assignments), 4)
        pct_expiry_risk = round(sum(1 for a in assignments if a.expiry_risk) / len(assignments), 4)
    else:
        avg_distance_km = 0.0
        max_distance_km = 0.0
        avg_utilization = 0.0
        total_cost_score = 0.0
        pct_expiry_risk = 0.0

    return {
        "algorithm": "hybrid",
        "algorithms_used": algorithms_used,
        "total_assigned": len(assignments),
        "total_unassigned": 0,
        "avg_distance_km": avg_distance_km,
        "max_distance_km": max_distance_km,
        "avg_technician_utilization": avg_utilization,
        "total_cost_score": total_cost_score,
        "pct_expiry_risk": pct_expiry_risk,
        "runtime_ms": runtime_ms,
    }


def hybrid_allocate(
    requests: List[RepairRequest],
    couriers: List[Technician],
    current_time: datetime,
    config: Dict[str, float] | None = None,
) -> Tuple[List[Assignment], List[RepairRequest], Dict[str, Any]]:
    """Allocate critical requests greedily and batch requests optimally."""
    critical_requests = [r for r in requests if r.urgency == RequestUrgency.critical]
    batch_requests = [r for r in requests if r.urgency != RequestUrgency.critical]

    LOGGER.info("hybrid_allocation_started", extra={"requests": len(requests), "couriers": len(couriers)})
    critical_assignments, critical_unassigned, critical_metrics = allocate_greedy(couriers, critical_requests, current_time, config)
    remaining_couriers = _update_availability(couriers, critical_assignments)

    if batch_requests:
        batch_assignments, batch_unassigned, batch_metrics = allocate_hungarian(remaining_couriers, batch_requests, current_time, config)
    else:
        batch_assignments, batch_unassigned, batch_metrics = [], [], {
            "total_assigned": 0,
            "total_unassigned": 0,
            "runtime_ms": 0.0,
        }

    algorithms_used = ["greedy", "hungarian"]
    if len(batch_requests) > 20:
        batch_assignments, batch_unassigned, batch_metrics = allocate_simulated_annealing(remaining_couriers, batch_requests, current_time, config)
        algorithms_used.append("sa")

    all_assignments = critical_assignments + batch_assignments
    all_unassigned = critical_unassigned + batch_unassigned
    runtime_ms = round(
        critical_metrics.get("runtime_ms", 0.0)
        + batch_metrics.get("runtime_ms", 0.0),
        2,
    )

    metrics = _combine_metrics(all_assignments, algorithms_used, runtime_ms)
    metrics["total_unassigned"] = len(all_unassigned)
    LOGGER.info("hybrid_allocation_finished", extra={"runtime_ms": runtime_ms, "assigned": len(all_assignments)})
    return all_assignments, all_unassigned, metrics
