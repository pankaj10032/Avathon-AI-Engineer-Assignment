"""Custom exceptions for allocation failures."""


class NoEligibleCourierError(Exception):
    """Raised when no courier can satisfy the hard constraints."""


class SampleExpiredError(Exception):
    """Raised when a request expires before assignment can complete."""


class CapacityExceededError(Exception):
    """Raised when a courier exceeds vehicle capacity."""
