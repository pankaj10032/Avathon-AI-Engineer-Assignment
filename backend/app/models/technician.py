from __future__ import annotations

from datetime import time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..config import MAX_MOTORCYCLE_SAMPLES, MAX_VAN_SAMPLES
from .common import AvailabilitySlot, Coordinate, VehicleType


class Courier(BaseModel):
    """Medical courier resource used by the allocation engine."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    vehicle_type: VehicleType
    location: Coordinate
    speed_kmh: float = Field(..., gt=0)
    active_samples_count: int = Field(..., ge=0)
    availability_schedule: list[AvailabilitySlot] = Field(default_factory=list)
    shift_start: time
    shift_end: time

    @model_validator(mode="before")
    @classmethod
    def fill_availability_schedule(cls, data: object) -> object:
        """Accept lean seed payloads and derive a default daily shift."""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if not normalized.get("availability_schedule") and normalized.get("shift_start") and normalized.get("shift_end"):
            normalized["availability_schedule"] = [
                {
                    "day": "daily",
                    "start": normalized["shift_start"],
                    "end": normalized["shift_end"],
                }
            ]
        return normalized

    @field_validator("active_samples_count")
    @classmethod
    def validate_capacity(cls, value: int, info: object) -> int:
        """Validate courier capacity against vehicle type."""
        vehicle_type = info.data.get("vehicle_type")
        if vehicle_type == VehicleType.motorcycle and value > MAX_MOTORCYCLE_SAMPLES:
            raise ValueError("motorcycle couriers can carry at most 3 active samples")
        if vehicle_type == VehicleType.van and value > MAX_VAN_SAMPLES:
            raise ValueError("van couriers can carry at most 8 active samples")
        return value

    @property
    def current_load(self) -> int:
        """Return the current number of samples assigned to the courier."""
        return self.active_samples_count

    @property
    def skills(self) -> list[str]:
        """Return sample types this courier can transport."""
        if self.vehicle_type == VehicleType.motorcycle:
            return ["blood", "biopsy"]
        return ["blood", "organ", "biopsy"]


# Backward-compatible alias for older code paths during the domain transition.
Technician = Courier
