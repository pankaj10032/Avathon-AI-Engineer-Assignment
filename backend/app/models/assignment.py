from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .common import AllocationAlgorithm


class Assignment(BaseModel):
    """Immutable allocation result for a courier-request pair."""

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    courier_id: str = Field(alias="technician_id")
    request_id: str
    score: float = Field(...)
    distance_km: float = Field(..., ge=0.0)
    algorithm_used: AllocationAlgorithm
    eta_minutes: float = Field(..., ge=0.0)
    expiry_risk: bool
    expiry_risk_level: str = Field(default="safe")
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    total_score: float = Field(default=0.0)
    explanation: str

    @property
    def technician_id(self) -> str:
        """Alias for courier_id to support legacy test paths."""
        return self.courier_id

