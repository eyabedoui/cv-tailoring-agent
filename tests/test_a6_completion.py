"""A6 — Verify successful completion and stop-rule priority."""

from agent.stop_rule import should_stop


def test_completed_workflow_stops_with_done():
    state = {
        "step_count": 4,
        "done": True,
        "match_score": 0.80,
        "user_rejected": False,
    }

    stop, reason = should_stop(state)

    assert stop is True
    assert reason == "done"


def test_completion_has_priority_over_max_steps():
    state = {
        "step_count": 12,
        "done": True,
    }

    stop, reason = should_stop(state)

    assert stop is True
    assert reason == "done"