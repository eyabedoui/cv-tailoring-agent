
"""A5 — Tests for safe, bounded agent tool retries."""

from unittest.mock import patch

import pytest

from agent.config import MAX_RETRIES_PER_TOOL
from agent.errors import make_error
from agent.loop import AgentLoop


@pytest.fixture
def agent():
    """Create an agent without running its model."""
    return AgentLoop(model=None)


def test_retryable_failure_recovers(agent):
    """A temporary failure should be retried successfully."""
    responses = [
        make_error("PORTAL_DOWN", "Temporary failure", retryable=True),
        {"job_id": "job_001", "title": "Python Developer"},
    ]

    with patch(
        "agent.loop.execute_tool",
        side_effect=responses,
    ) as execute:
        result = agent._execute_with_retries(
            "read_job_posting",
            {"url": "https://example.com/job"},
        )

    assert result["job_id"] == "job_001"
    assert execute.call_count == 2


def test_retry_limit_is_respected(agent):
    """Persistent failures must stop after the configured retry limit."""
    error = make_error(
        "PORTAL_DOWN",
        "Still unavailable",
        retryable=True,
    )

    with patch(
        "agent.loop.execute_tool",
        return_value=error,
    ) as execute:
        result = agent._execute_with_retries(
            "read_job_posting",
            {"url": "https://example.com/job"},
        )

    assert result["error"] == "PORTAL_DOWN"
    assert execute.call_count == 1 + MAX_RETRIES_PER_TOOL


def test_non_retryable_error_runs_once(agent):
    """An explicit non-retryable failure must not be retried."""
    error = make_error(
        "BAD_RESPONSE",
        "Invalid response",
        retryable=False,
    )

    with patch(
        "agent.loop.execute_tool",
        return_value=error,
    ) as execute:
        agent._execute_with_retries("read_job_posting", {})

    assert execute.call_count == 1


@pytest.mark.parametrize(
    "error_code",
    ["SITE_BLOCKED", "SITE_NOT_ALLOWED"],
)
def test_blocked_sites_never_retry(agent, error_code):
    """Site restrictions override even an incorrect retryable flag."""
    error = make_error(
        error_code,
        "Site access prohibited",
        retryable=True,
    )

    with patch(
        "agent.loop.execute_tool",
        return_value=error,
    ) as execute:
        agent._execute_with_retries("read_job_posting", {})

    assert execute.call_count == 1


def test_submission_never_retries(agent):
    """An application must never be automatically submitted twice."""
    error = make_error(
        "PORTAL_DOWN",
        "Submission outcome unknown",
        retryable=True,
    )

    with patch(
        "agent.loop.execute_tool",
        return_value=error,
    ) as execute:
        result = agent._execute_with_retries(
            "submit_application",
            {"job_id": "job_001"},
        )

    assert result["error"] == "PORTAL_DOWN"
    assert execute.call_count == 1


def test_successful_execution_does_not_retry(agent):
    """Successful operations must run exactly once."""
    with patch(
        "agent.loop.execute_tool",
        return_value={"status": "success"},
    ) as execute:
        result = agent._execute_with_retries(
            "read_job_posting",
            {"url": "https://example.com/job"},
        )

    assert result["status"] == "success"
    assert execute.call_count == 1
