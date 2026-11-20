
"""A6 — An always-failing tool must not keep the agent running forever."""

from unittest.mock import patch

from agent.config import MAX_STEPS
from agent.errors import make_error
from agent.loop import AgentLoop


class AlwaysCallingModel:
    """Simulate a model that continually requests the same tool."""

    def call_model(self, messages, tools):
        return {
            "type": "tool_call",
            "tool_name": "read_job_posting",
            "arguments": {"url": "https://example.com/job"},
        }


def test_always_failing_tool_eventually_stops(tmp_path):
    """Repeated tool failures must trigger the repeated-call stop rule."""

    model = AlwaysCallingModel()

    error = make_error(
        "PORTAL_DOWN",
        "Simulated permanent outage",
        retryable=False,
    )

    with patch(
        "agent.loop.execute_tool",
        return_value=error,
    ) as execute:
        result = AgentLoop(model).run()

    assert result["stop_reason"] == "repeated_call"
    assert result["step_count"] <= MAX_STEPS
    assert execute.call_count == result["step_count"]


def test_always_failing_tool_never_updates_job_state():
    """A failed read must not be stored as a valid job."""

    model = AlwaysCallingModel()

    error = make_error(
        "PORTAL_DOWN",
        "Simulated permanent outage",
        retryable=False,
    )

    with patch(
        "agent.loop.execute_tool",
        return_value=error,
    ):
        result = AgentLoop(model).run()

    assert result["state"]["job"] is None
