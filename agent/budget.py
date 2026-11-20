
"""
Budget tracking for paid API requests.

The default budget is zero until spending is approved.
"""

from threading import Lock


class BudgetExceededError(RuntimeError):
    """Raised when a request would exceed the spending limit."""


class BudgetTracker:
    def __init__(self, limit_usd: float):
        if limit_usd < 0:
            raise ValueError("Budget cannot be negative.")

        self.limit_usd = limit_usd
        self.spent_usd = 0.0
        self.reserved_usd = 0.0
        self._lock = Lock()

    @property
    def remaining_usd(self) -> float:
        with self._lock:
            return max(
                0.0,
                self.limit_usd - self.spent_usd - self.reserved_usd,
            )

    def reserve(self, estimated_cost_usd: float) -> None:
        """Reserve enough budget before making an API request."""
        if estimated_cost_usd <= 0:
            raise ValueError("Estimated cost must be positive.")

        with self._lock:
            remaining = (
                self.limit_usd - self.spent_usd - self.reserved_usd
            )

            if estimated_cost_usd > remaining:
                raise BudgetExceededError(
                    "API budget exceeded. Paid request blocked."
                )

            self.reserved_usd += estimated_cost_usd

    def settle(
        self,
        reserved_cost_usd: float,
        actual_cost_usd: float,
    ) -> None:
        """Replace a reservation with the actual request cost."""
        if reserved_cost_usd <= 0 or actual_cost_usd < 0:
            raise ValueError("Invalid cost values.")

        with self._lock:
            if reserved_cost_usd > self.reserved_usd:
                raise ValueError("Reservation does not exist.")

            self.reserved_usd -= reserved_cost_usd
            self.spent_usd += actual_cost_usd

    def release(self, reserved_cost_usd: float) -> None:
        """Release a reservation when a request was not charged."""
        if reserved_cost_usd <= 0:
            raise ValueError("Reservation must be positive.")

        with self._lock:
            if reserved_cost_usd > self.reserved_usd:
                raise ValueError("Reservation does not exist.")

            self.reserved_usd -= reserved_cost_usd
