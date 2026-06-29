from __future__ import annotations

"""FastAPI application for the resource allocation engine."""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.algorithms import allocate_greedy, allocate_hungarian, allocate_simulated_annealing, hybrid_allocate
from app.models.assignment import Assignment
from app.models.sample_request import SampleRequest
from app.models.courier import Courier
from app.reoptimizer import handle_urgent_arrival
from app.steps import greedy_assignment_steps

LOGGER = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
SEED_DIR = DATA_DIR / "original"
TECHNICIANS_FILE = DATA_DIR / "technicians.json"
REQUESTS_FILE = DATA_DIR / "repair_requests.json"
ASSIGNMENTS_FILE = DATA_DIR / "assignments.json"
SEED_TECHNICIANS_FILE = SEED_DIR / "technicians.json"
SEED_REQUESTS_FILE = SEED_DIR / "repair_requests.json"
SEED_ASSIGNMENTS_FILE = SEED_DIR / "assignments.json"


class AllocateRequest(BaseModel):
    """Request body for allocation endpoints."""

    algorithm: Literal["greedy", "hungarian", "both", "sa", "hybrid"] = Field(default="greedy")
    weights: Dict[str, float] | None = None


class UrgentRequestPayload(BaseModel):
    """Request body for urgent re-optimization events."""

    new_request: SampleRequest
    current_assignments: List[Assignment] = Field(default_factory=list)


def _load_json(path: Path) -> Any:
    """Load JSON data from disk."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    """Write JSON data to disk."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _load_technicians() -> List[Courier]:
    """Load the active courier dataset."""
    return [Courier.model_validate(item) for item in _load_json(TECHNICIANS_FILE)]


def _load_requests() -> List[SampleRequest]:
    """Load the active request dataset."""
    return [SampleRequest.model_validate(item) for item in _load_json(REQUESTS_FILE)]


def _load_assignments() -> List[Assignment]:
    """Load persisted assignments if available."""
    if not ASSIGNMENTS_FILE.exists():
        return []
    return [Assignment.model_validate(item) for item in _load_json(ASSIGNMENTS_FILE)]


def _default_data_payload() -> Dict[str, Any]:
    """Build the default data payload for the frontend."""
    return {
        "technicians": _load_json(TECHNICIANS_FILE),
        "requests": _load_json(REQUESTS_FILE),
        "assignments": _load_json(ASSIGNMENTS_FILE) if ASSIGNMENTS_FILE.exists() else [],
    }


def _reset_from_seed() -> None:
    """Restore active data from seed files, shifting request timestamps to now."""
    from datetime import datetime, timezone, timedelta
    _write_json(TECHNICIANS_FILE, _load_json(SEED_TECHNICIANS_FILE))

    # Shift request created_at timestamps so they are fresh relative to now
    seed_requests = _load_json(SEED_REQUESTS_FILE)
    if seed_requests:
        # Find the earliest created_at in the seed data
        seed_times = [datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) for r in seed_requests]
        earliest = min(seed_times)
        now = datetime.now(timezone.utc)
        # Shift so the earliest request was created 2 minutes ago
        base_offset = now - earliest - timedelta(minutes=2)
        for r in seed_requests:
            original = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
            shifted = original + base_offset
            r["created_at"] = shifted.strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_json(REQUESTS_FILE, seed_requests)

    if SEED_ASSIGNMENTS_FILE.exists():
        _write_json(ASSIGNMENTS_FILE, _load_json(SEED_ASSIGNMENTS_FILE))


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Refresh seed data with current timestamps on server start."""
    if SEED_TECHNICIANS_FILE.exists() and SEED_REQUESTS_FILE.exists():
        _reset_from_seed()
        LOGGER.info("seed_data_refreshed_on_startup")
    yield


app = FastAPI(title="Resource Allocation Engine", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> Dict[str, Any]:
    """Return a friendly landing payload for direct browser visits."""
    return {
        "service": "Resource Allocation Engine API",
        "status": "ok",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health() -> Dict[str, str]:
    """Return a basic health response."""
    return {"status": "ok"}


@app.get("/api/data")
def get_data() -> Dict[str, Any]:
    """Return technicians, requests, and assignments."""
    return _default_data_payload()


@app.post("/api/allocate")
def allocate(payload: AllocateRequest) -> Dict[str, Any]:
    """Run the selected allocation algorithm and return results."""
    LOGGER.info("allocation_request_started", extra={"algorithm": payload.algorithm})
    technicians = _load_technicians()
    requests = _load_requests()
    from datetime import datetime, timezone
    current_time = datetime.now(timezone.utc)

    if payload.algorithm == "greedy":
        assignments, unassigned, metrics = allocate_greedy(technicians, requests, current_time, payload.weights)
        return {
            "algorithm": "greedy",
            "assignments": [a.model_dump(by_alias=True) for a in assignments],
            "unassigned_requests": [r.model_dump() for r in unassigned],
            "metrics": metrics,
        }

    if payload.algorithm == "hungarian":
        assignments, unassigned, metrics = allocate_hungarian(technicians, requests, current_time, payload.weights)
        return {
            "algorithm": "hungarian",
            "assignments": [a.model_dump(by_alias=True) for a in assignments],
            "unassigned_requests": [r.model_dump() for r in unassigned],
            "metrics": metrics,
        }

    if payload.algorithm == "sa":
        assignments, unassigned, metrics = allocate_simulated_annealing(technicians, requests, current_time, payload.weights)
        return {
            "algorithm": "simulated_annealing",
            "assignments": [a.model_dump(by_alias=True) for a in assignments],
            "unassigned_requests": [r.model_dump() for r in unassigned],
            "metrics": metrics,
        }

    if payload.algorithm == "hybrid":
        assignments, unassigned, metrics = hybrid_allocate(requests, technicians, current_time, payload.weights)
        return {
            "algorithm": "hybrid",
            "assignments": [a.model_dump(by_alias=True) for a in assignments],
            "unassigned_requests": [r.model_dump() for r in unassigned],
            "metrics": metrics,
        }

    greedy_assignments, greedy_unassigned, greedy_metrics = allocate_greedy(technicians, requests, current_time, payload.weights)
    hungarian_assignments, hungarian_unassigned, hungarian_metrics = allocate_hungarian(technicians, requests, current_time, payload.weights)
    sa_assignments, sa_unassigned, sa_metrics = allocate_simulated_annealing(technicians, requests, current_time, payload.weights)
    hybrid_assignments, hybrid_unassigned, hybrid_metrics = hybrid_allocate(requests, technicians, current_time, payload.weights)

    return {
        "algorithm": "both",
        "results": {
            "greedy": {
                "assignments": [a.model_dump(by_alias=True) for a in greedy_assignments],
                "unassigned_requests": [r.model_dump() for r in greedy_unassigned],
                "metrics": greedy_metrics,
            },
            "hungarian": {
                "assignments": [a.model_dump(by_alias=True) for a in hungarian_assignments],
                "unassigned_requests": [r.model_dump() for r in hungarian_unassigned],
                "metrics": hungarian_metrics,
            },
            "simulated_annealing": {
                "assignments": [a.model_dump(by_alias=True) for a in sa_assignments],
                "unassigned_requests": [r.model_dump() for r in sa_unassigned],
                "metrics": sa_metrics,
            },
            "hybrid": {
                "assignments": [a.model_dump(by_alias=True) for a in hybrid_assignments],
                "unassigned_requests": [r.model_dump() for r in hybrid_unassigned],
                "metrics": hybrid_metrics,
            },
        },
    }


@app.post("/api/reset")
def reset_data() -> Dict[str, str]:
    """Restore sample data from the seed snapshot."""
    if not SEED_TECHNICIANS_FILE.exists() or not SEED_REQUESTS_FILE.exists():
        raise HTTPException(status_code=404, detail="Seed data files not found")

    _reset_from_seed()

    return {"status": "reset", "message": "Sample data reloaded"}


@app.post("/api/urgent-request")
def urgent_request(payload: UrgentRequestPayload) -> Dict[str, Any]:
    """Handle urgent request arrivals and possible re-optimization."""
    LOGGER.info(
        "urgent_reoptimization_triggered",
        extra={"request_id": payload.new_request.id, "urgency": payload.new_request.urgency.value},
    )
    technicians = _load_technicians()
    current_time = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    request_lookup = {request.id: request for request in _load_requests()}
    updated_assignments, meta = handle_urgent_arrival(
        payload.new_request,
        payload.current_assignments,
        technicians,
        current_time,
        request_lookup,
    )
    return {
        "assignments": [a.model_dump(by_alias=True) for a in updated_assignments],
        "meta": meta,
    }


@app.get("/api/allocate/steps")
def allocate_steps(algorithm: Literal["greedy"] = "greedy") -> Dict[str, Any]:
    """Return ordered greedy steps for animation."""
    technicians = _load_technicians()
    requests = _load_requests()
    from datetime import datetime, timezone
    current_time = datetime.now(timezone.utc)

    if algorithm != "greedy":
        raise HTTPException(status_code=400, detail="Only greedy steps are supported")

    return {
        "algorithm": algorithm,
        "steps": greedy_assignment_steps(technicians, requests, current_time),
        "current_time": current_time.isoformat(),
    }
