from __future__ import annotations

import sys
from datetime import datetime, time, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.common import AvailabilitySlot, Coordinate, RequestStatus, RequestUrgency, TimeWindow, VehicleType
from app.models.repair_request import RepairRequest
from app.models.technician import Technician


@pytest.fixture
def current_time() -> datetime:
    """Return a stable UTC time for algorithm tests."""
    return datetime(2026, 6, 28, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def motorcycle_courier() -> Technician:
    """Return a motorcycle courier fixture."""
    return Technician(
        id="courier-1",
        name="Moto One",
        vehicle_type=VehicleType.motorcycle,
        location=Coordinate(lat=19.0760, lng=72.8777),
        speed_kmh=42.0,
        active_samples_count=2,
        availability_schedule=[AvailabilitySlot(day="Monday", start=time(8, 0), end=time(20, 0))],
        shift_start=time(8, 0),
        shift_end=time(20, 0),
    )


@pytest.fixture
def van_courier() -> Technician:
    """Return a van courier fixture."""
    return Technician(
        id="courier-2",
        name="Van One",
        vehicle_type=VehicleType.van,
        location=Coordinate(lat=19.0810, lng=72.8820),
        speed_kmh=35.0,
        active_samples_count=1,
        availability_schedule=[AvailabilitySlot(day="Monday", start=time(8, 0), end=time(20, 0))],
        shift_start=time(8, 0),
        shift_end=time(20, 0),
    )


@pytest.fixture
def courier_fleet(motorcycle_courier: Technician, van_courier: Technician) -> list[Technician]:
    """Return a small mixed courier fleet."""
    return [motorcycle_courier, van_courier]


@pytest.fixture
def critical_request() -> RepairRequest:
    """Return a critical request fixture."""
    return RepairRequest(
        id="req-critical",
        hospital_name="City Hospital",
        location=Coordinate(lat=19.0805, lng=72.8785),
        sample_type="blood",
        urgency=RequestUrgency.critical,
        priority=5,
        expiry_minutes=15,
        created_at=datetime(2026, 6, 28, 8, 55, tzinfo=timezone.utc),
        status=RequestStatus.open,
        time_window=TimeWindow(start=time(8, 0), end=time(10, 0)),
    )


@pytest.fixture
def normal_request() -> RepairRequest:
    """Return a normal request fixture."""
    return RepairRequest(
        id="req-normal",
        hospital_name="Metro Hospital",
        location=Coordinate(lat=19.0890, lng=72.8900),
        sample_type="biopsy",
        urgency=RequestUrgency.normal,
        priority=1,
        expiry_minutes=45,
        created_at=datetime(2026, 6, 28, 8, 30, tzinfo=timezone.utc),
        status=RequestStatus.open,
        time_window=TimeWindow(start=time(9, 0), end=time(11, 0)),
    )


@pytest.fixture
def organ_request() -> RepairRequest:
    """Return an organ request fixture."""
    return RepairRequest(
        id="req-organ",
        hospital_name="Central Hospital",
        location=Coordinate(lat=19.0725, lng=72.8650),
        sample_type="organ",
        urgency=RequestUrgency.high,
        priority=3,
        expiry_minutes=30,
        created_at=datetime(2026, 6, 28, 8, 40, tzinfo=timezone.utc),
        status=RequestStatus.open,
        time_window=TimeWindow(start=time(9, 0), end=time(12, 0)),
    )


@pytest.fixture
def sample_requests(critical_request: RepairRequest, normal_request: RepairRequest, organ_request: RepairRequest) -> list[RepairRequest]:
    """Return a small request set for algorithm tests."""
    return [critical_request, normal_request, organ_request]


@pytest.fixture
def simple_3x3_fleet() -> list[Technician]:
    """Return a 3x3 courier fleet for optimality tests."""
    return [
        Technician(
            id="courier-a",
            name="A",
            vehicle_type=VehicleType.van,
            location=Coordinate(lat=19.0000, lng=72.8000),
            speed_kmh=40.0,
            active_samples_count=0,
            availability_schedule=[AvailabilitySlot(day="Monday", start=time(8, 0), end=time(20, 0))],
            shift_start=time(8, 0),
            shift_end=time(20, 0),
        ),
        Technician(
            id="courier-b",
            name="B",
            vehicle_type=VehicleType.van,
            location=Coordinate(lat=19.0100, lng=72.8100),
            speed_kmh=40.0,
            active_samples_count=0,
            availability_schedule=[AvailabilitySlot(day="Monday", start=time(8, 0), end=time(20, 0))],
            shift_start=time(8, 0),
            shift_end=time(20, 0),
        ),
        Technician(
            id="courier-c",
            name="C",
            vehicle_type=VehicleType.van,
            location=Coordinate(lat=19.0200, lng=72.8200),
            speed_kmh=40.0,
            active_samples_count=0,
            availability_schedule=[AvailabilitySlot(day="Monday", start=time(8, 0), end=time(20, 0))],
            shift_start=time(8, 0),
            shift_end=time(20, 0),
        ),
    ]


@pytest.fixture
def simple_3x3_requests() -> list[RepairRequest]:
    """Return a 3x3 request set for optimality tests."""
    return [
        RepairRequest(
            id="req-a",
            hospital_name="A",
            location=Coordinate(lat=19.0002, lng=72.8002),
            sample_type="blood",
            urgency=RequestUrgency.normal,
            priority=1,
            expiry_minutes=60,
            created_at=datetime(2026, 6, 28, 8, 0, tzinfo=timezone.utc),
            status=RequestStatus.open,
            time_window=TimeWindow(start=time(8, 30), end=time(11, 0)),
        ),
        RepairRequest(
            id="req-b",
            hospital_name="B",
            location=Coordinate(lat=19.0102, lng=72.8102),
            sample_type="blood",
            urgency=RequestUrgency.normal,
            priority=1,
            expiry_minutes=60,
            created_at=datetime(2026, 6, 28, 8, 0, tzinfo=timezone.utc),
            status=RequestStatus.open,
            time_window=TimeWindow(start=time(8, 30), end=time(11, 0)),
        ),
        RepairRequest(
            id="req-c",
            hospital_name="C",
            location=Coordinate(lat=19.0202, lng=72.8202),
            sample_type="blood",
            urgency=RequestUrgency.normal,
            priority=1,
            expiry_minutes=60,
            created_at=datetime(2026, 6, 28, 8, 0, tzinfo=timezone.utc),
            status=RequestStatus.open,
            time_window=TimeWindow(start=time(8, 30), end=time(11, 0)),
        ),
    ]
