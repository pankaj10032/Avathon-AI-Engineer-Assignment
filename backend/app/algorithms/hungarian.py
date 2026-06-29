from __future__ import annotations

"""Hungarian batch allocation strategy."""

import logging
import time as time_module
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.models.assignment import Assignment
from app.models.common import AllocationAlgorithm
from app.models.sample_request import SampleRequest
from app.models.courier import Courier
from app.algorithms.greedy import _availability_overlap_score
from app.utils.distance import haversine_km, travel_time_minutes
from app.utils.scorer import score_assignment, explain_assignment

LOGGER = logging.getLogger(__name__)
INFEASIBLE_COST = 1_000_000.0


@dataclass(frozen=True)
class _MatrixCell:
    cost: float
    distance_km: float
    eta_minutes: float
    technician: Courier
    request: SampleRequest
    is_feasible: bool


def _normalize_distance(distance_km: float, max_distance_km: float) -> float:
    """Normalize distance so closer couriers score higher."""
    if max_distance_km <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - (distance_km / max_distance_km)))


def _workload_penalty(current_load: int, max_load: int) -> float:
    """Convert current load to a normalized penalty."""
    if max_load <= 0:
        return 0.0
    return min(1.0, current_load / max_load)


def _build_matrix(
    technicians: List[Courier],
    requests: List[SampleRequest],
    current_time: datetime,
    config: dict[str, float] | None = None,
) -> Tuple[np.ndarray, List[List[_MatrixCell]]]:
    """Build the cost matrix and associated metadata, duplicating couriers by remaining capacity."""
    max_distance_km = 0.0
    for tech in technicians:
        for request in requests:
            max_distance_km = max(
                max_distance_km,
                haversine_km(tech.location, request.location),
            )

    cells: List[List[_MatrixCell]] = []
    matrix_rows = []

    for tech in technicians:
        max_cap = 3 if tech.vehicle_type.value == "motorcycle" else 8
        remaining_capacity = max_cap - tech.active_samples_count
        if remaining_capacity <= 0:
            continue

        for slot in range(remaining_capacity):
            row: List[_MatrixCell] = []
            row_costs = []
            tech_state = tech.model_copy(update={"active_samples_count": tech.active_samples_count + slot})
            for request in requests:
                if request.required_skill not in tech_state.skills:
                    cell = _MatrixCell(INFEASIBLE_COST, np.inf, np.inf, tech_state, request, False)
                    row.append(cell)
                    row_costs.append(INFEASIBLE_COST)
                    continue

                availability_score = _availability_overlap_score(tech_state.availability_schedule, request.time_window)
                if availability_score <= 0:
                    cell = _MatrixCell(INFEASIBLE_COST, np.inf, np.inf, tech_state, request, False)
                    row.append(cell)
                    row_costs.append(INFEASIBLE_COST)
                    continue

                distance_km = haversine_km(tech_state.location, request.location)
                eta_minutes = travel_time_minutes(tech_state.location, request.location, tech_state.speed_kmh, current_time)
                score = score_assignment(tech_state, request, current_time, config)
                if not score.is_feasible:
                    cell = _MatrixCell(INFEASIBLE_COST, np.inf, eta_minutes, tech_state, request, False)
                    row.append(cell)
                    row_costs.append(INFEASIBLE_COST)
                    continue

                cost = 1.0 - score.total_score
                cell = _MatrixCell(round(cost, 4), round(distance_km, 2), round(eta_minutes, 2), tech_state, request, True)
                row.append(cell)
                row_costs.append(cell.cost)
            cells.append(row)
            matrix_rows.append(row_costs)

    if not matrix_rows:
        return np.empty((0, len(requests))), []

    return np.array(matrix_rows, dtype=float), cells


def _assignment_explanation(
    tech: Courier,
    request: SampleRequest,
    distance_km: float,
    eta_minutes: float,
    cost: float,
    expiry_risk: bool,
) -> str:
    """Create a human-readable explanation for a Hungarian assignment."""
    risk_phrase = "expiry risk" if expiry_risk else "within expiry window"
    return (
        f"Assigned {tech.name} to {request.id} "
        f"({distance_km:.1f}km away, ETA {eta_minutes:.1f} min, optimal batch match, "
        f"cost={cost:.3f}, {risk_phrase})"
    )


def allocate_hungarian(
    technicians: List[Courier],
    requests: List[SampleRequest],
    current_time: datetime,
    config: dict[str, float] | None = None,
) -> Tuple[List[Assignment], List[SampleRequest], Dict[str, Any]]:
    """
    Batch optimal allocation using the Hungarian algorithm.
    Produces one best global assignment per technician/request pair when feasible.
    """
    start_time = time_module.perf_counter()
    LOGGER.info("hungarian_allocation_started", extra={"requests": len(requests), "technicians": len(technicians)})

    if not technicians or not requests:
        metrics = {
            "algorithm": AllocationAlgorithm.hungarian.value,
            "total_assigned": 0,
            "total_unassigned": len(requests),
            "avg_distance_km": 0.0,
            "max_distance_km": 0.0,
            "avg_technician_utilization": 0.0,
            "total_cost_score": 0.0,
            "runtime_ms": round((time_module.perf_counter() - start_time) * 1000.0, 2),
        }
        return [], list(requests), metrics

    cost_matrix, cells = _build_matrix(technicians, requests, current_time, config)
    if cost_matrix.size == 0:
        metrics = {
            "algorithm": AllocationAlgorithm.hungarian.value,
            "total_assigned": 0,
            "total_unassigned": len(requests),
            "avg_distance_km": 0.0,
            "max_distance_km": 0.0,
            "avg_technician_utilization": 0.0,
            "total_cost_score": 0.0,
            "pct_expiry_risk": 0.0,
            "runtime_ms": round((time_module.perf_counter() - start_time) * 1000.0, 2),
        }
        return [], list(requests), metrics

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    assignments: List[Assignment] = []
    assigned_request_ids = set()
    total_distance = 0.0
    total_cost = 0.0

    for r, c in zip(row_ind, col_ind):
        cell = cells[r][c]
        if not cell.is_feasible or not np.isfinite(cost_matrix[r, c]):
            continue

        assigned_request_ids.add(cell.request.id)
        total_distance += cell.distance_km
        total_cost += float(cost_matrix[r, c])
        score = score_assignment(cell.technician, cell.request, current_time, config)

        assignments.append(
            Assignment(
                technician_id=cell.technician.id,
                request_id=cell.request.id,
                score=round(score.total_score, 4),
                distance_km=cell.distance_km,
                algorithm_used=AllocationAlgorithm.hungarian,
                eta_minutes=cell.eta_minutes,
                expiry_risk=score.expiry_risk_level in {"warning", "critical"},
                expiry_risk_level=score.expiry_risk_level,
                score_breakdown=score.breakdown,
                total_score=score.total_score,
                explanation=explain_assignment(score, cell.technician, cell.request),
            )
        )
        LOGGER.info(
            "assignment_decision",
            extra={
                "courier_id": cell.technician.id,
                "request_id": cell.request.id,
                "score": round(score.total_score, 4),
                "reason": "minimum_batch_cost",
            },
        )

    unassigned = [request for request in requests if request.id not in assigned_request_ids]

    avg_distance_km = round(total_distance / len(assignments), 2) if assignments else 0.0
    max_distance_km = round(max((a.distance_km for a in assignments), default=0.0), 2)

    final_loads = {tech.id: tech.current_load for tech in technicians}
    for assignment in assignments:
        final_loads[assignment.courier_id] += 1

    utilizations = []
    for tech in technicians:
        final_load = final_loads[tech.id]
        utilizations.append((final_load - tech.current_load) / final_load if final_load > 0 else 0.0)

    metrics: Dict[str, Any] = {
        "algorithm": AllocationAlgorithm.hungarian.value,
        "total_assigned": len(assignments),
        "total_unassigned": len(unassigned),
        "avg_distance_km": avg_distance_km,
        "max_distance_km": max_distance_km,
        "avg_technician_utilization": round(sum(utilizations) / len(utilizations), 4) if utilizations else 0.0,
        "total_cost_score": round(total_cost, 4),
        "pct_expiry_risk": round(
            sum(1 for a in assignments if a.expiry_risk) / len(assignments), 4
        )
        if assignments
        else 0.0,
        "runtime_ms": round((time_module.perf_counter() - start_time) * 1000.0, 2),
    }
    LOGGER.info("hungarian_allocation_finished", extra={"runtime_ms": metrics["runtime_ms"], "assigned": len(assignments)})

    return assignments, unassigned, metrics
