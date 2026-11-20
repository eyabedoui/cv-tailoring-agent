
import pytest

from agent.budget import BudgetTracker, BudgetExceededError


def test_initial_budget():
    tracker = BudgetTracker(5.0)

    assert tracker.limit_usd == 5.0
    assert tracker.spent_usd == 0.0
    assert tracker.remaining_usd == 5.0


def test_negative_budget_rejected():
    with pytest.raises(ValueError):
        BudgetTracker(-1.0)


def test_reserve_budget():
    tracker = BudgetTracker(5.0)

    tracker.reserve(2.0)

    assert tracker.reserved_usd == 2.0
    assert tracker.remaining_usd == 3.0


def test_budget_exceeded():
    tracker = BudgetTracker(1.0)

    with pytest.raises(BudgetExceededError):
        tracker.reserve(2.0)


def test_zero_budget_blocks_requests():
    tracker = BudgetTracker(0.0)

    with pytest.raises(BudgetExceededError):
        tracker.reserve(0.01)


def test_settle_actual_cost():
    tracker = BudgetTracker(5.0)

    tracker.reserve(2.0)
    tracker.settle(2.0, 1.5)

    assert tracker.reserved_usd == 0.0
    assert tracker.spent_usd == 1.5
    assert tracker.remaining_usd == 3.5


def test_release_reservation():
    tracker = BudgetTracker(5.0)

    tracker.reserve(2.0)
    tracker.release(2.0)

    assert tracker.reserved_usd == 0.0
    assert tracker.remaining_usd == 5.0


def test_multiple_reservations():
    tracker = BudgetTracker(5.0)

    tracker.reserve(2.0)
    tracker.reserve(1.0)

    assert tracker.reserved_usd == 3.0
    assert tracker.remaining_usd == 2.0


def test_invalid_reservation():
    tracker = BudgetTracker(5.0)

    with pytest.raises(ValueError):
        tracker.reserve(0.0)


def test_invalid_settlement():
    tracker = BudgetTracker(5.0)

    with pytest.raises(ValueError):
        tracker.settle(1.0, -1.0)


def test_over_reservation_rejected():
    tracker = BudgetTracker(5.0)

    tracker.reserve(1.0)

    with pytest.raises(ValueError):
        tracker.release(2.0)
