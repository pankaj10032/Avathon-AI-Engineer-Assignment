from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.algorithms import allocate_greedy
from app.models.common import Coordinate, RequestStatus, RequestUrgency, TimeWindow, VehicleType
from app.models.repair_request import RepairRequest
from app.models.technician import Technician
from app.utils.urgency import flag_expiry_risk


def test_expired_request_not_assigned(courier_fleet):
    current_time = datetime(2026, 6, 28, 10, 0, tzinfo=timezone.utc)
    expired_request = RepairRequest(
        id="expired-1",
        hospital_name="Old Hospital",
        location=Coordinate(lat=19.0760, lng=72.8777),
        sample_type="blood",
        urgency=RequestUrgency.normal,
        expiry_minutes=10,
        created_at=current_time - timedelta(minutes=25),
        status=RequestStatus.open,
        time_window=TimeWindow(start=current_time.time(), end=(current_time + timedelta(hours=1)).time()),
    )

    assignments, unassigned, _ = allocate_greedy(courier_fleet, [expired_request], current_time)

    assert assignments == []
    assert unassigned[0].id == "expired-1"


def test_skill_mismatch_blocked(motorcycle_courier):
    current_time = datetime(2026, 6, 28, 10, 0, tzinfo=timezone.utc)
    organ_request = RepairRequest(
        id="organ-1",
        hospital_name="Organ Center",
        location=Coordinate(lat=19.0800, lng=72.8780),
        sample_type="organ",
        urgency=RequestUrgency.high,
        expiry_minutes=30,
        created_at=current_time,
        status=RequestStatus.open,
        time_window=TimeWindow(start=current_time.time(), end=(current_time + timedelta(hours=1)).time()),
    )

    assignments, unassigned, _ = allocate_greedy([motorcycle_courier], [organ_request], current_time)

    assert assignments == []
    assert unassigned[0].id == "organ-1"
    assert motorcycle_courier.vehicle_type == VehicleType.motorcycle


def test_unavailable_courier_blocked():
    current_time = datetime(2026, 6, 28, 10, 0, tzinfo=timezone.utc)
    courier = Technician(
        id="late-courier",
        name="Late Rider",
        vehicle_type=VehicleType.van,
        location=Coordinate(lat=19.0760, lng=72.8777),
        speed_kmh=35.0,
        active_samples_count=0,
        shift_start=current_time.replace(hour=12).time(),
        shift_end=current_time.replace(hour=18).time(),
    )
    request = RepairRequest(
        id="req-1",
        hospital_name="Shift Test",
        location=Coordinate(lat=19.0780, lng=72.8790),
        sample_type="organ",
        urgency=RequestUrgency.normal,
        expiry_minutes=30,
        created_at=current_time,
        status=RequestStatus.open,
        time_window=TimeWindow(start=current_time.time(), end=(current_time + timedelta(hours=1)).time()),
    )

    assignments, unassigned, _ = allocate_greedy([courier], [request], current_time)

    assert assignments == []
    assert unassigned[0].id == "req-1"


@pytest.mark.parametrize(
    "eta_minutes, expected",
    [(7.5, False), (8.5, True)],
)
def test_expiry_risk_flagged(eta_minutes, expected):
    current_time = datetime(2026, 6, 28, 10, 0, tzinfo=timezone.utc)
    request = RepairRequest(
        id="risk-1",
        hospital_name="Risk Hospital",
        location=Coordinate(lat=19.0780, lng=72.8790),
        sample_type="blood",
        urgency=RequestUrgency.critical,
        expiry_minutes=10,
        created_at=current_time,
        status=RequestStatus.open,
        time_window=TimeWindow(start=current_time.time(), end=(current_time + timedelta(hours=1)).time()),
    )

    assert flag_expiry_risk(request, eta_minutes, current_time) is expected
