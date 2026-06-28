"""Shared configuration constants for allocation algorithms."""

DISTANCE_WEIGHT: float = 0.40
WORKLOAD_WEIGHT: float = 0.30
AVAILABILITY_WEIGHT: float = 0.30
MAX_MOTORCYCLE_SAMPLES: int = 3
MAX_VAN_SAMPLES: int = 8
MAX_COURIER_SPEED_KMH: float = 60.0
MAX_REASONABLE_DISTANCE_KM: float = 30.0
SCORE_DISTANCE_WEIGHT: float = 0.20
SCORE_SPEED_WEIGHT: float = 0.15
SCORE_CAPACITY_WEIGHT: float = 0.15
SCORE_ETA_WEIGHT: float = 0.25
SCORE_EXPIRY_RISK_WEIGHT: float = 0.25

SA_INITIAL_TEMP: float = 100.0
SA_COOLING_RATE: float = 0.995
SA_ITERATIONS: int = 2000


def _assert_weights_sum_to_one() -> None:
    """Ensure the scorer weights remain normalized."""
    total = (
        SCORE_DISTANCE_WEIGHT
        + SCORE_SPEED_WEIGHT
        + SCORE_CAPACITY_WEIGHT
        + SCORE_ETA_WEIGHT
        + SCORE_EXPIRY_RISK_WEIGHT
    )
    assert abs(total - 1.0) < 1e-9, "Scoring weights must sum to 1.0"


_assert_weights_sum_to_one()
