from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import Coordinate, RequestUrgency, RequestStatus, TimeWindow


class SampleRequest(BaseModel):
    """Hospital sample pickup request."""

    model_config = ConfigDict(frozen=True)

    id: str
    hospital_name: str
    location: Coordinate
    sample_type: str = Field(..., description="blood, organ, or biopsy")
    urgency: RequestUrgency
    priority: int = Field(default=1, ge=1, le=5)
    expiry_minutes: int = Field(..., gt=0)
    created_at: datetime
    time_window: TimeWindow
    status: RequestStatus = RequestStatus.open

    @model_validator(mode="before")
    @classmethod
    def fill_derived_fields(cls, data: object) -> object:
        """Accept lean seed/API payloads and derive scheduler fields."""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        urgency_priority = {"critical": 5, "high": 3, "normal": 1}

        if "priority" not in normalized:
            normalized["priority"] = urgency_priority.get(str(normalized.get("urgency", "normal")), 1)

        if "time_window" not in normalized and normalized.get("created_at") and normalized.get("expiry_minutes"):
            created_at = normalized["created_at"]
            if not isinstance(created_at, datetime):
                created_at = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            end_time = created_at + timedelta(minutes=int(normalized["expiry_minutes"]))
            normalized["time_window"] = {
                "start": created_at.time().replace(tzinfo=None),
                "end": end_time.time().replace(tzinfo=None),
            }

        return normalized

    @field_validator("expiry_minutes")
    @classmethod
    def validate_expiry_minutes(cls, value: int) -> int:
        """Ensure requests have a positive expiry window."""
        if value <= 0:
            raise ValueError("expiry_minutes must be greater than 0")
        return value

    @property
    def required_skill(self) -> str:
        """Return the required courier skill for this request."""
        return self.sample_type

