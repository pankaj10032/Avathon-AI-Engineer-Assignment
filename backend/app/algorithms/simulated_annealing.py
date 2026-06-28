from __future__ import annotations

"""Simulated annealing allocation strategy."""

import math
import random
import logging
import time as time_module
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Tuple

from app.config import SA_COOLING_RATE, SA_INITIAL_TEMP, SA_ITERATIONS
from app.models.assignment import Assignment
from app.models.common import AllocationAlgorithm, RequestUrgency
from app.models.repair_request import RepairRequest
from app.models.technician import Technician
from app.utils.distance import haversine_km, travel_time_minutes
from app.utils.scorer import explain_assignment, score_assignment
from app.utils.urgency import compute_urgency_score

LOGGER = logging.getLogger(__name__)


def _within_shift(courier: Technician, current_time: datetime) -> bool:
    """Return True when the courier is on shift."""
    current_t = current_time.time()
    return courier.shift_start <= current_t <= courier.shift_end


def _courier_capacity(courier: Technician) -> int:
    """Return the maximum sample capacity for a courier."""
    return 3 if courier.vehicle_type.value == "motorcycle" else 8


def _build_feasible_pairs(
    couriers: List[Technician],
    requests: List[RepairRequest],
    current_time: datetime,
    config: dict[str, float] | None = None,
) -> dict[str, list[tuple[str, float, float, float]]]:
    """Build feasible courier options for each request."""
    pairs: dict[str, list[tuple[str, float, float, float]]] = {}
    for request in requests:
        options: list[tuple[str, float, float, float]] = []
        for courier in couriers:
            if not _within_shift(courier, current_time):
                continue
            if courier.active_samples_count >= _courier_capacity(courier):
                continue

            distance_km = haversine_km(courier.location, request.location)
            eta_minutes = travel_time_minutes(courier.location, request.location, courier.speed_kmh, current_time)
            score = score_assignment(courier, request, current_time, config)
            if not score.is_feasible:
                continue

            base_cost = 1.0 - score.total_score
            options.append((courier.id, round(distance_km, 2), round(eta_minutes, 2), round(base_cost, 4)))
        pairs[request.id] = options
    return pairs


def _choose_best_initial_assignment(
    request: RepairRequest,
    options: list[tuple[str, float, float, float]],
) -> str | None:
    """Pick the best courier for a request from feasible options."""
    if not options:
        return None
    return min(options, key=lambda item: item[3])[0]


def _build_initial_state(
    couriers: List[Technician],
    requests: List[RepairRequest],
    pair_map: dict[str, list[tuple[str, float, float, float]]],
    current_time: datetime,
) -> dict[str, str | None]:
    """Build the greedy-seeded initial state for annealing."""
    state: dict[str, str | None] = {request.id: None for request in requests}
    courier_loads = {courier.id: courier.active_samples_count for courier in couriers}
    capacities = {courier.id: _courier_capacity(courier) for courier in couriers}

    sorted_requests = sorted(
        requests,
        key=lambda r: (r.urgency != RequestUrgency.critical, r.expiry_minutes, r.created_at),
    )

    for request in sorted_requests:
        options = [
            opt for opt in pair_map.get(request.id, [])
            if courier_loads[opt[0]] < capacities[opt[0]]
        ]
        # Prefer the earliest-expiring requests first when seeding from greedy.
        _ = compute_urgency_score(request, current_time)
        best_choice = _choose_best_initial_assignment(request, options)
        if best_choice is not None:
            state[request.id] = best_choice
            courier_loads[best_choice] += 1

    return state


def _state_cost(
    state: dict[str, str | None],
    request_map: dict[str, RepairRequest],
    courier_map: dict[str, Technician],
    pair_map: dict[str, list[tuple[str, float, float, float]]],
    current_time: datetime,
    config: dict[str, float] | None = None,
) -> float:
    """Compute the total cost of a candidate state."""
    total_cost = 0.0
    for request_id, courier_id in state.items():
        request = request_map[request_id]
        if courier_id is None:
            total_cost += 25.0
            continue
        options = {cid: (dist, eta, cost) for cid, dist, eta, cost in pair_map.get(request_id, [])}
        if courier_id not in options:
            total_cost += 50.0
            continue
        distance_km, eta_minutes, base_cost = options[courier_id]
        score = score_assignment(courier_map[courier_id], request, current_time, config)
        total_cost += base_cost + (1.0 - score.total_score)
        if score.expiry_risk_level in {"warning", "critical"}:
            total_cost += 20.0
    return round(total_cost, 4)


def _state_to_assignments(
    state: dict[str, str | None],
    request_map: dict[str, RepairRequest],
    courier_map: dict[str, Technician],
    pair_map: dict[str, list[tuple[str, float, float, float]]],
    current_time: datetime,
    config: dict[str, float] | None = None,
) -> tuple[list[Assignment], list[RepairRequest], float, float]:
    """Convert a state into assignments, unassigned requests, and cost."""
    assignments: list[Assignment] = []
    unassigned: list[RepairRequest] = []
    total_cost = 0.0

    options_lookup = {
        request_id: {courier_id: (dist, eta, cost) for courier_id, dist, eta, cost in options}
        for request_id, options in pair_map.items()
    }

    for request_id, courier_id in state.items():
        request = request_map[request_id]
        if courier_id is None:
            unassigned.append(request)
            continue

        dist_eta_cost = options_lookup.get(request_id, {}).get(courier_id)
        if dist_eta_cost is None:
            unassigned.append(request)
            continue

        distance_km, eta_minutes, _ = dist_eta_cost
        score_result = score_assignment(courier_map[courier_id], request, current_time, config)
        expiry_risk = score_result.expiry_risk_level in {"warning", "critical"}
        score = score_result.total_score
        total_cost += 1.0 - score

        assignments.append(
            Assignment(
                technician_id=courier_id,
                request_id=request_id,
                score=round(score, 4),
                distance_km=round(distance_km, 2),
                algorithm_used=AllocationAlgorithm.simulated_annealing,
                eta_minutes=round(eta_minutes, 2),
                expiry_risk=expiry_risk,
                expiry_risk_level=score_result.expiry_risk_level,
                score_breakdown=score_result.breakdown,
                total_score=score,
                explanation=explain_assignment(score_result, courier_map[courier_id], request),
            )
        )

    pct_expiry_risk = round(sum(1 for a in assignments if a.expiry_risk) / len(assignments), 4) if assignments else 0.0
    return assignments, unassigned, round(total_cost, 4), pct_expiry_risk


def allocate_simulated_annealing(
    couriers: List[Technician],
    requests: List[RepairRequest],
    current_time: datetime,
    config: dict[str, float] | None = None,
) -> Tuple[List[Assignment], List[RepairRequest], Dict[str, Any]]:
    """Simulated annealing seeded from greedy and optimized by cost."""
    start_time = time_module.perf_counter()
    LOGGER.info("sa_allocation_started", extra={"requests": len(requests), "couriers": len(couriers)})
    if not couriers or not requests:
        return [], list(requests), {
            "algorithm": AllocationAlgorithm.simulated_annealing.value,
            "total_assigned": 0,
            "total_unassigned": len(requests),
            "avg_distance_km": 0.0,
            "max_distance_km": 0.0,
            "avg_technician_utilization": 0.0,
            "total_cost_score": 0.0,
            "pct_expiry_risk": 0.0,
            "cost_history": [],
            "improvement_pct": 0.0,
            "runtime_ms": round((time_module.perf_counter() - start_time) * 1000.0, 2),
        }

    request_map = {request.id: request for request in requests}
    courier_map = {courier.id: courier for courier in couriers}
    pair_map = _build_feasible_pairs(couriers, requests, current_time, config)

    current_state = _build_initial_state(couriers, requests, pair_map, current_time)
    current_cost = _state_cost(current_state, request_map, courier_map, pair_map, current_time, config)
    best_state = dict(current_state)
    best_cost = current_cost
    greedy_cost = current_cost
    temperature = SA_INITIAL_TEMP
    cost_history: list[float] = []

    request_ids = list(request_map.keys())
    courier_ids = list(courier_map.keys())

    for _ in range(SA_ITERATIONS):
        proposal = dict(current_state)
        assigned_requests = [rid for rid, cid in proposal.items() if cid is not None]

        if len(assigned_requests) >= 2 and random.random() < 0.5:
            r1, r2 = random.sample(assigned_requests, 2)
            proposal[r1], proposal[r2] = proposal[r2], proposal[r1]
        else:
            request_id = random.choice(request_ids)
            feasible = pair_map.get(request_id, [])
            if feasible and random.random() < 0.85:
                proposal[request_id] = random.choice(feasible)[0]
            else:
                proposal[request_id] = None

        courier_counts: dict[str, int] = {cid: 0 for cid in courier_ids}
        for _, cid in proposal.items():
            if cid is not None:
                courier_counts[cid] += 1

        for cid, count in list(courier_counts.items()):
            cap = _courier_capacity(courier_map[cid])
            if count > cap:
                overflow = count - cap
                assigned_here = [rid for rid, pcid in proposal.items() if pcid == cid]
                random.shuffle(assigned_here)
                for rid in assigned_here[:overflow]:
                    proposal[rid] = None

        proposal_cost = _state_cost(proposal, request_map, courier_map, pair_map, current_time, config)
        cost_history.append(round(proposal_cost, 4))

        delta_cost = proposal_cost - current_cost
        accept = delta_cost <= 0 or random.random() < math.exp(-delta_cost / max(temperature, 1e-9))
        if accept:
            current_state = proposal
            current_cost = proposal_cost

        if proposal_cost < best_cost:
            best_state = dict(proposal)
            best_cost = proposal_cost

        temperature *= SA_COOLING_RATE

    assignments, unassigned, total_cost, pct_expiry_risk = _state_to_assignments(
        best_state, request_map, courier_map, pair_map, current_time, config
    )

    avg_distance_km = round(sum(a.distance_km for a in assignments) / len(assignments), 2) if assignments else 0.0
    max_distance_km = round(max((a.distance_km for a in assignments), default=0.0), 2)
    final_loads = {courier.id: courier.active_samples_count for courier in couriers}
    for assignment in assignments:
        final_loads[assignment.courier_id] += 1
    utilizations = []
    for courier in couriers:
        final_load = final_loads[courier.id]
        utilizations.append((final_load - courier.active_samples_count) / final_load if final_load > 0 else 0.0)

    improvement_pct = round(((greedy_cost - best_cost) / greedy_cost) * 100.0, 2) if greedy_cost > 0 else 0.0

    metrics: Dict[str, Any] = {
        "algorithm": AllocationAlgorithm.simulated_annealing.value,
        "total_assigned": len(assignments),
        "total_unassigned": len(unassigned),
        "avg_distance_km": avg_distance_km,
        "max_distance_km": max_distance_km,
        "avg_technician_utilization": round(sum(utilizations) / len(utilizations), 4) if utilizations else 0.0,
        "total_cost_score": round(best_cost, 4),
        "pct_expiry_risk": pct_expiry_risk,
        "cost_history": cost_history,
        "improvement_pct": improvement_pct,
        "runtime_ms": round((time_module.perf_counter() - start_time) * 1000.0, 2),
    }
    LOGGER.info("sa_allocation_finished", extra={"runtime_ms": metrics["runtime_ms"], "assigned": len(assignments)})

    return assignments, unassigned, metrics
