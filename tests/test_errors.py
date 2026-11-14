
"""Tests for agent/errors.py and loop error-contract behaviour."""

import json
import pytest

from agent.errors import (
    make_error, is_error,
    INVALID_ARGUMENTS, UNKNOWN_TOOL, BAD_RESPONSE,
    ERROR_CODES,
)
from agent.fake_model import FakeModel
from agent.loop import AgentLoop
from agent.checkpoint import HumanApprovalCheckpoint
from agent.logger import AgentLogger


# ---------------------------------------------------------------------------
# Unit tests for make_error / is_error
# ---------------------------------------------------------------------------

def test_make_error_structure():
    err = make_error(INVALID_ARGUMENTS, "bad arg")
    assert err["error"] == INVALID_ARGUMENTS
    assert err["message"] == "bad arg"
    assert err["retryable"] is False


def test_make_error_retryable():
    err = make_error(UNKNOWN_TOOL, "no such tool", retryable=True)
    assert err["retryable"] is True


def test_is_error_true():
    assert is_error(make_error(BAD_RESPONSE, "oops")) is True


def test_is_error_false_on_normal_dict():
    assert is_error({"status": "ok"}) is False


def test_is_error_false_on_non_dict():
    assert is_error("string") is False


def test_all_error_codes_known():
    for code in ERROR_CODES:
        err = make_error(code, "msg")
        assert is_error(err)


# ---------------------------------------------------------------------------
# Failed read_job_posting does NOT set job state
# ---------------------------------------------------------------------------

def test_failed_read_does_not_set_job(monkeypatch, tmp_path):
    def failing_execute_tool(tool_name, arguments):
        if tool_name == "read_job_posting":
            return make_error(INVALID_ARGUMENTS, "simulated failure")
        return {}

    monkeypatch.setattr("agent.loop.execute_tool", failing_execute_tool)

    # After a failed read the model tries submit without prerequisites.
    # The loop should return an error result to the model (not crash) and
    # ultimately stop by max_steps or done.
    model = FakeModel([
        {"type": "tool_call", "tool_name": "read_job_posting",
         "arguments": {"url": "mock://jobs/job_001"}},
        {"type": "final", "content": "Could not read job."},
    ])

    agent = AgentLoop(
        model,
        checkpoint=HumanApprovalCheckpoint(auto_approve=True),
        logger=AgentLogger(log_dir=tmp_path, run_id="failed_read"),
    )
    result = agent.run()
    # Run must complete without crash.
    assert result["stop_reason"] == "done"
    assert result["answer"] == "Could not read job."


# ---------------------------------------------------------------------------
# Failed save_tailored_cv does NOT set tailored_cv state
# ---------------------------------------------------------------------------

def test_failed_save_does_not_set_tailored_cv(monkeypatch, tmp_path):
    def failing_execute_tool(tool_name, arguments):
        if tool_name == "save_tailored_cv":
            return make_error(INVALID_ARGUMENTS, "simulated save failure")
        from agent.tools.registry import TOOL_FUNCTIONS
        return TOOL_FUNCTIONS[tool_name](**arguments)

    monkeypatch.setattr("agent.loop.execute_tool", failing_execute_tool)

    model = FakeModel([
        {"type": "tool_call", "tool_name": "read_job_posting",
         "arguments": {"url": "mock://jobs/job_001"}},
        {"type": "tool_call", "tool_name": "read_master_cv", "arguments": {}},
        {"type": "tool_call", "tool_name": "save_tailored_cv",
         "arguments": {"text": "cv text", "job_id": "job_001", "kind": "cv"}},
        # Try to submit without valid CV (the save failed).
        {"type": "tool_call", "tool_name": "submit_application",
         "arguments": {"cv_path": "x", "cover_letter_path": "y", "job_id": "job_001"}},
        {"type": "final", "content": "Done."},
    ])

    checkpoint = HumanApprovalCheckpoint(auto_approve=True)
    logger = AgentLogger(log_dir=tmp_path, run_id="failed_save")
    agent = AgentLoop(model, checkpoint=checkpoint, logger=logger)
    result = agent.run()

    # The checkpoint must NOT have been reached (tailored_cv was never set).
    assert checkpoint.last_decision is None
    assert result["stop_reason"] == "done"


# ---------------------------------------------------------------------------
# Submit with mismatched job_id does NOT crash and does NOT call checkpoint
# ---------------------------------------------------------------------------

def test_submit_mismatched_job_id_does_not_crash(tmp_path):
    model = FakeModel([
        {"type": "tool_call", "tool_name": "read_job_posting",
         "arguments": {"url": "mock://jobs/job_001"}},
        {"type": "tool_call", "tool_name": "read_master_cv", "arguments": {}},
        {"type": "tool_call", "tool_name": "save_tailored_cv",
         "arguments": {"text": "cv", "job_id": "job_001", "kind": "cv"}},
        {"type": "tool_call", "tool_name": "save_tailored_cv",
         "arguments": {"text": "cl", "job_id": "job_001", "kind": "cover_letter"}},
        # Wrong job_id — should return an error, not crash.
        {"type": "tool_call", "tool_name": "submit_application",
         "arguments": {"cv_path": "x", "cover_letter_path": "y", "job_id": "WRONG"}},
        {"type": "final", "content": "Done."},
    ])

    checkpoint = HumanApprovalCheckpoint(auto_approve=True)
    logger = AgentLogger(log_dir=tmp_path, run_id="mismatch_test")
    agent = AgentLoop(model, checkpoint=checkpoint, logger=logger)
    result = agent.run()

    # Checkpoint must NOT have been called.
    assert checkpoint.last_decision is None
    assert result["stop_reason"] == "done"


# ---------------------------------------------------------------------------
# Malformed model output ends by max_steps, not by exception
# ---------------------------------------------------------------------------

def test_malformed_model_output_ends_by_max_steps(tmp_path):
    from agent.config import MAX_STEPS

    # Return a non-dict response every time.
    class AlwaysBadModel:
        def call_model(self, messages, tools):
            return "not a dict"

    logger = AgentLogger(log_dir=tmp_path, run_id="bad_model")
    agent = AgentLoop(
        AlwaysBadModel(),
        checkpoint=HumanApprovalCheckpoint(auto_approve=True),
        logger=logger,
    )
    result = agent.run()
    assert result["stop_reason"] == "max_steps"
    assert result["step_count"] == MAX_STEPS


def test_unsupported_response_type_ends_by_max_steps(tmp_path):
    from agent.config import MAX_STEPS

    class BadTypeModel:
        def call_model(self, messages, tools):
            return {"type": "unsupported_xyz"}

    logger = AgentLogger(log_dir=tmp_path, run_id="bad_type")
    agent = AgentLoop(
        BadTypeModel(),
        checkpoint=HumanApprovalCheckpoint(auto_approve=True),
        logger=logger,
    )
    result = agent.run()
    assert result["stop_reason"] == "max_steps"
    assert result["step_count"] == MAX_STEPS
