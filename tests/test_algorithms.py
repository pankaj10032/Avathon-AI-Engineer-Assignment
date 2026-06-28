from __future__ import annotations

import pytest

from app.algorithms import allocate_greedy, allocate_hungarian, allocate_simulated_annealing, hybrid_allocate
from app.models.common import VehicleType


def test_greedy_respects_capacity(courier_fleet, sample_requests, current_time):
    assignments, _, _ = allocate_greedy(courier_fleet, sample_requests, current_time)

    motorcycle_assignments = [assignment for assignment in assignments if assignment.technician_id == "courier-1"]
    assert len(motorcycle_assignments) <= 1
    assert courier_fleet[0].vehicle_type == VehicleType.motorcycle


def test_greedy_critical_first(courier_fleet, sample_requests, current_time):
    assignments, _, _ = allocate_greedy(courier_fleet, sample_requests, current_time)
    assigned_order = [assignment.request_id for assignment in assignments]

    assert assigned_order[0] == "req-critical"
    assert "req-critical" in assigned_order


def test_hungarian_global_optimal(simple_3x3_fleet, simple_3x3_requests, current_time):
    greedy_assignments, _, greedy_metrics = allocate_greedy(simple_3x3_fleet, simple_3x3_requests, current_time)
    hungarian_assignments, _, hungarian_metrics = allocate_hungarian(
        simple_3x3_fleet,
        simple_3x3_requests,
        current_time,
    )

    assert len(hungarian_assignments) == 3
    assert hungarian_metrics["total_cost_score"] <= greedy_metrics["total_cost_score"]
    assert hungarian_metrics["total_cost_score"] == pytest.approx(
        sum(1.0 - assignment.score for assignment in hungarian_assignments),
        rel=1e-3,
    )


def test_sa_improves_greedy(courier_fleet, sample_requests, current_time):
    _, _, greedy_metrics = allocate_greedy(courier_fleet, sample_requests, current_time)
    _, _, sa_metrics = allocate_simulated_annealing(courier_fleet, sample_requests, current_time)

    assert sa_metrics["total_cost_score"] <= greedy_metrics["total_cost_score"]
    assert sa_metrics["runtime_ms"] >= 0


def test_hybrid_uses_greedy_for_critical(monkeypatch, courier_fleet, sample_requests, current_time):
    captured = {}

    def fake_greedy(couriers, requests, current):
        captured["request_ids"] = [request.id for request in requests]
        return [], [], {"runtime_ms": 1.0, "total_cost_score": 0.0, "total_assigned": 0, "total_unassigned": 0}

    def fake_hungarian(couriers, requests, current):
        return [], [], {"runtime_ms": 1.0, "total_cost_score": 0.0, "total_assigned": 0, "total_unassigned": 0}

    monkeypatch.setattr("app.algorithms.hybrid.allocate_greedy", fake_greedy)
    monkeypatch.setattr("app.algorithms.hybrid.allocate_hungarian", fake_hungarian)
    monkeypatch.setattr("app.algorithms.hybrid.allocate_simulated_annealing", fake_hungarian)

    hybrid_allocate(sample_requests, courier_fleet, current_time)

    assert captured["request_ids"] == ["req-critical"]


def test_all_algorithms_same_input(courier_fleet, sample_requests, current_time):
    results = [
        allocate_greedy(courier_fleet, sample_requests, current_time),
        allocate_hungarian(courier_fleet, sample_requests, current_time),
        allocate_simulated_annealing(courier_fleet, sample_requests, current_time),
        hybrid_allocate(sample_requests, courier_fleet, current_time),
    ]

    for result in results:
        assert result is not None
