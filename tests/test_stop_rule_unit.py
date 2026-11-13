
import pytest

from agent.stop_rule import should_stop
from agent.config import MAX_STEPS


def test_stops_at_max_steps():
    state = {
        "step_count": MAX_STEPS,
    }

    stop, reason = should_stop(state)

    assert stop is True
    assert reason == "max_steps"


def test_stops_on_no_match():
    state = {
        "step_count": 3,
        "match_score": 0.20,
    }

    stop, reason = should_stop(state)

    assert stop is True
    assert reason == "no_match"


def test_stops_on_three_identical_calls():
    state = {
        "step_count": 3,
        "identical_call_count": 3,
    }

    stop, reason = should_stop(state)

    assert stop is True
    assert reason == "repeated_call"


def test_stops_when_user_rejects():
    state = {
        "step_count": 5,
        "user_rejected": True,
    }

    stop, reason = should_stop(state)

    assert stop is True
    assert reason == "user_rejected"


def test_does_not_stop_during_normal_run():
    state = {
        "step_count": 4,
        "match_score": 0.75,
        "identical_call_count": 1,
        "user_rejected": False,
        "done": False,
    }

    stop, reason = should_stop(state)

    assert stop is False
    assert reason is None


def test_threshold_boundary_does_not_stop():
    state = {
        "step_count": 3,
        "match_score": 0.25,
    }

    stop, reason = should_stop(state)

    assert stop is False
    assert reason is None
