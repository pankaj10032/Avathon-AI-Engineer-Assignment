from __future__ import annotations

from datetime import datetime, time, timezone

import pytest
from fastapi.testclient import TestClient

from app.models.assignment import Assignment
from app.models.common import Coordinate, RequestStatus, RequestUrgency, TimeWindow, VehicleType
from app.models.repair_request import RepairRequest
from app.models.technician import Technician
from main import app

client = TestClient(app)


@pytest.fixture
def api_technicians() -> list[Technician]:
    """Return technicians for API tests."""
    return [
        Technician(
            id="api-1",
            name="API One",
            vehicle_type=VehicleType.van,
            location=Coordinate(lat=19.0760, lng=72.8777),
            speed_kmh=40.0,
            active_samples_count=0,
            availability_schedule=[],
            shift_start=time(8, 0),
            shift_end=time(20, 0),
        ),
        Technician(
            id="api-2",
            name="API Two",
            vehicle_type=VehicleType.van,
            location=Coordinate(lat=19.0810, lng=72.8820),
            speed_kmh=38.0,
            active_samples_count=0,
            availability_schedule=[],
            shift_start=time(8, 0),
            shift_end=time(20, 0),
        ),
    ]


@pytest.fixture
def api_requests() -> list[RepairRequest]:
    """Return requests for API tests."""
    now = datetime(2026, 6, 28, 9, 0, tzinfo=timezone.utc)
    return [
        RepairRequest(
            id="api-r1",
            hospital_name="Hosp 1",
            location=Coordinate(lat=19.0763, lng=72.8780),
            sample_type="blood",
            urgency=RequestUrgency.critical,
            expiry_minutes=20,
            created_at=now,
            status=RequestStatus.open,
            time_window=TimeWindow(start=time(8, 30), end=time(10, 0)),
        ),
        RepairRequest(
            id="api-r2",
            hospital_name="Hosp 2",
            location=Coordinate(lat=19.0820, lng=72.8830),
            sample_type="biopsy",
            urgency=RequestUrgency.normal,
            expiry_minutes=45,
            created_at=now,
            status=RequestStatus.open,
            time_window=TimeWindow(start=time(9, 0), end=time(11, 0)),
        ),
    ]


@pytest.fixture
def patch_data(monkeypatch, api_technicians, api_requests):
    """Patch backend data loaders for deterministic API tests."""
    monkeypatch.setattr("main._load_technicians", lambda: api_technicians)
    monkeypatch.setattr("main._load_requests", lambda: api_requests)
    monkeypatch.setattr("main._load_json", lambda path: [])
    monkeypatch.setattr("main._reset_from_seed", lambda: None)
    return api_technicians, api_requests


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_allocate_greedy(patch_data):
    response = client.post("/api/allocate", json={"algorithm": "greedy"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["algorithm"] == "greedy"
    assert isinstance(payload["assignments"], list)
    assert "metrics" in payload


def test_allocate_all_algorithms(patch_data):
    response = client.post("/api/allocate", json={"algorithm": "both"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["algorithm"] == "both"
    assert set(payload["results"].keys()) == {"greedy", "hungarian", "simulated_annealing", "hybrid"}


def test_urgent_request_triggers_reoptimization(monkeypatch, patch_data, api_requests):
    current_assignments = [
        Assignment(
            technician_id="api-1",
            request_id="api-r2",
            score=0.9,
            distance_km=1.2,
            algorithm_used="greedy",
            eta_minutes=5.0,
            expiry_risk=False,
            explanation="existing assignment",
        )
    ]

    monkeypatch.setattr(
        "main.handle_urgent_arrival",
        lambda new_request, assignments, couriers, current_time, request_lookup: (
            [
                Assignment(
                    technician_id="api-1",
                    request_id=new_request.id,
                    score=0.8,
                    distance_km=1.0,
                    algorithm_used="greedy",
                    eta_minutes=4.0,
                    expiry_risk=True,
                    explanation="reoptimized",
                )
            ],
            {"reoptimized": True, "preempted_request": "api-r2"},
        ),
    )

    response = client.post(
        "/api/urgent-request",
        json={
            "new_request": api_requests[0].model_dump(),
            "current_assignments": current_assignments,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["reoptimized"] is True
    assert payload["meta"]["preempted_request"] == "api-r2"


def test_invalid_request_rejected():
    response = client.post("/api/allocate", json={})
    assert response.status_code == 422
