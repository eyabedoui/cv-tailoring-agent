
import json
import time

import pytest

from agent.fake_model import FakeModel
from agent.loop import AgentLoop
from agent.config import MAX_STEPS


def test_agent_loop_executes_tool_and_returns_final_answer():
    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "final",
            "content": "The CV has been read.",
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    assert result["answer"] == "The CV has been read."
    assert result["stop_reason"] == "done"


def test_agent_loop_wraps_tool_results_as_untrusted_data():
    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "final",
            "content": "Done.",
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    messages = result["messages"]

    assert any(
        '<tool_result untrusted="true">' in message.get("content", "")
        for message in messages
    )


def test_agent_loop_continues_when_match_score_is_above_threshold():
    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "match_skills",
            "arguments": {
                "cv_text": "Python, SQL",
                "job": {"title": "Junior AI Engineer"},
            },
        },
        {
            "type": "final",
            "content": "Matching completed.",
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    assert result["answer"] == "Matching completed."
    assert result["stop_reason"] == "done"


def test_agent_loop_stops_when_match_score_is_too_low(monkeypatch):
    def fake_execute_tool(tool_name, arguments):
        if tool_name == "match_skills":
            return {
                "match_score": 0.10,
                "matched_skills": [],
                "missing_skills": ["Python"],
            }

        return {}

    monkeypatch.setattr(
        "agent.loop.execute_tool",
        fake_execute_tool,
    )

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "match_skills",
            "arguments": {
                "cv_text": "Java",
                "job": {"title": "Junior AI Engineer"},
            },
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    assert result["stop_reason"] == "no_match"
    assert result["step_count"] == 1


def test_agent_loop_stops_after_three_identical_calls():
    repeated_call = {
        "type": "tool_call",
        "tool_name": "read_master_cv",
        "arguments": {},
    }

    model = FakeModel([
        repeated_call,
        repeated_call,
        repeated_call,
    ])

    agent = AgentLoop(model)
    result = agent.run()

    assert result["stop_reason"] == "repeated_call"


def test_agent_loop_blocks_submission_when_user_rejects(
    monkeypatch,
    tmp_path,
):
    from agent.checkpoint import HumanApprovalCheckpoint
    from agent.logger import AgentLogger
    from agent.tools.registry import execute_tool as real_execute_tool

    executed_tools = []

    def tracking_execute_tool(tool_name, arguments):
        executed_tools.append(tool_name)
        return real_execute_tool(tool_name, arguments)

    monkeypatch.setattr(
        "agent.loop.execute_tool",
        tracking_execute_tool,
    )

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_job_posting",
            "arguments": {
                "url": "mock://jobs/job_001",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Tailored CV content",
                "job_id": "job_001",
                "kind": "cv",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Dear Hiring Manager.",
                "job_id": "job_001",
                "kind": "cover_letter",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "submit_application",
            "arguments": {
                "cv_path": "sandbox/output/job_001_cv.txt",
                "cover_letter_path": "sandbox/output/job_001_cover_letter.txt",
                "job_id": "job_001",
            },
        },
    ])

    checkpoint = HumanApprovalCheckpoint(auto_reject=True)

    logger = AgentLogger(
        log_dir=tmp_path,
        run_id="rejection_test",
    )

    agent = AgentLoop(
        model,
        logger=logger,
        checkpoint=checkpoint,
    )

    result = agent.run()

    assert result["stop_reason"] == "user_rejected"
    assert "submit_application" not in executed_tools
    assert checkpoint.last_decision is False

def test_agent_loop_submits_application_after_user_approves(
    monkeypatch,
    tmp_path,
):
    from agent.checkpoint import HumanApprovalCheckpoint
    from agent.logger import AgentLogger
    from agent.tools.registry import execute_tool as real_execute_tool

    executed_tools = []

    def tracking_execute_tool(tool_name, arguments):
        executed_tools.append(tool_name)
        return real_execute_tool(tool_name, arguments)

    monkeypatch.setattr(
        "agent.loop.execute_tool",
        tracking_execute_tool,
    )

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_job_posting",
            "arguments": {
                "url": "mock://jobs/job_001",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Tailored CV content",
                "job_id": "job_001",
                "kind": "cv",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Dear Hiring Manager.",
                "job_id": "job_001",
                "kind": "cover_letter",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "submit_application",
            "arguments": {
                "cv_path": "sandbox/output/job_001_cv.txt",
                "cover_letter_path": "sandbox/output/job_001_cover_letter.txt",
                "job_id": "job_001",
            },
        },
        {
            "type": "final",
            "content": "Application submitted successfully.",
        },
    ])

    checkpoint = HumanApprovalCheckpoint(auto_approve=True)

    logger = AgentLogger(
        log_dir=tmp_path,
        run_id="approval_test",
    )

    agent = AgentLoop(
        model,
        logger=logger,
        checkpoint=checkpoint,
    )

    result = agent.run()

    # Submission must actually be executed after approval.
    assert "submit_application" in executed_tools

    # The checkpoint must record approval.
    assert checkpoint.last_decision is True

    # The agent must continue and return the final response.
    assert result["answer"] == "Application submitted successfully."
    assert result["stop_reason"] == "done"

    # Verify that the approval decision was written to the log.
    import json

    log_file = tmp_path / "approval_test.jsonl"
    events = [
        json.loads(line)
        for line in log_file.read_text(encoding="utf-8").splitlines()
    ]

    checkpoint_events = [
        event for event in events
        if event["event"] == "human_checkpoint"
    ]

    assert len(checkpoint_events) == 1
    assert checkpoint_events[0]["approved"] is True


# ---------------------------------------------------------------------------
# Requirement 1: failed read_job_posting — job not stored, submit blocked
# ---------------------------------------------------------------------------

def test_loop_failed_read_does_not_store_job_and_blocks_submit(
    monkeypatch, tmp_path
):
    """
    When read_job_posting returns an error:
    - job is not stored in loop state
    - a later submit_application does not raise (submit gate blocks it)
    - the checkpoint is never called
    - the model receives the read error as a tool message
    - the submit gate returns INVALID_ARGUMENTS (missing prerequisites)
    """
    from agent.checkpoint import HumanApprovalCheckpoint
    from agent.logger import AgentLogger
    from agent.errors import make_error, NOT_FOUND

    def patched_execute(tool_name, arguments):
        if tool_name == "read_job_posting":
            return make_error(NOT_FOUND, "simulated: posting not found")
        from agent.tools.registry import TOOL_FUNCTIONS
        return TOOL_FUNCTIONS[tool_name](**arguments)

    monkeypatch.setattr("agent.loop.execute_tool", patched_execute)

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_job_posting",
            "arguments": {"url": "mock://jobs/job_001"},
        },
        # After failed read, model immediately tries to submit.
        {
            "type": "tool_call",
            "tool_name": "submit_application",
            "arguments": {
                "cv_path": "x.txt",
                "cover_letter_path": "y.txt",
                "job_id": "job_001",
            },
        },
        {
            "type": "final",
            "content": "Could not proceed: job posting unavailable.",
        },
    ])

    checkpoint = HumanApprovalCheckpoint(auto_approve=True)
    logger = AgentLogger(log_dir=tmp_path, run_id="failed_read_loop")
    agent = AgentLoop(model, logger=logger, checkpoint=checkpoint)

    result = agent.run()

    # Run completes without exception.
    assert result["stop_reason"] == "done"

    # Checkpoint was never reached (job was never stored; submit blocked).
    assert checkpoint.last_decision is None

    # The model received the read error as a tool result.
    read_tool_msgs = [
        m for m in result["messages"]
        if m.get("role") == "tool" and m.get("name") == "read_job_posting"
    ]
    assert len(read_tool_msgs) == 1
    assert '"error"' in read_tool_msgs[0]["content"]

    # Submit was blocked with INVALID_ARGUMENTS (missing prerequisites).
    submit_tool_msgs = [
        m for m in result["messages"]
        if m.get("role") == "tool" and m.get("name") == "submit_application"
    ]
    assert len(submit_tool_msgs) == 1
    assert '"INVALID_ARGUMENTS"' in submit_tool_msgs[0]["content"]


# ---------------------------------------------------------------------------
# Requirement 2: failed save_tailored_cv — CV not recorded, submit blocked
# ---------------------------------------------------------------------------

def test_loop_failed_save_tailored_cv_blocks_submit(monkeypatch, tmp_path):
    """
    When save_tailored_cv returns an error:
    - tailored_cv is not recorded in loop state
    - a later submit_application is blocked with INVALID_ARGUMENTS
    - the checkpoint is never called
    """
    from agent.checkpoint import HumanApprovalCheckpoint
    from agent.logger import AgentLogger
    from agent.errors import make_error, INVALID_ARGUMENTS

    def patched_execute(tool_name, arguments):
        if tool_name == "save_tailored_cv" and arguments.get("kind") == "cv":
            return make_error(INVALID_ARGUMENTS, "simulated: save failed")
        from agent.tools.registry import TOOL_FUNCTIONS
        return TOOL_FUNCTIONS[tool_name](**arguments)

    monkeypatch.setattr("agent.loop.execute_tool", patched_execute)

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_job_posting",
            "arguments": {"url": "mock://jobs/job_001"},
        },
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Tailored content",
                "job_id": "job_001",
                "kind": "cv",
            },
        },
        # Tries to submit; tailored_cv was never stored.
        {
            "type": "tool_call",
            "tool_name": "submit_application",
            "arguments": {
                "cv_path": "x.txt",
                "cover_letter_path": "y.txt",
                "job_id": "job_001",
            },
        },
        {
            "type": "final",
            "content": "Save failed; application not submitted.",
        },
    ])

    checkpoint = HumanApprovalCheckpoint(auto_approve=True)
    logger = AgentLogger(log_dir=tmp_path, run_id="failed_save_loop")
    agent = AgentLoop(model, logger=logger, checkpoint=checkpoint)

    result = agent.run()

    assert result["stop_reason"] == "done"

    # Checkpoint never called — submit was blocked before reaching it.
    assert checkpoint.last_decision is None

    # Submit was blocked with INVALID_ARGUMENTS.
    submit_tool_msgs = [
        m for m in result["messages"]
        if m.get("role") == "tool" and m.get("name") == "submit_application"
    ]
    assert len(submit_tool_msgs) == 1
    assert '"INVALID_ARGUMENTS"' in submit_tool_msgs[0]["content"]


# ---------------------------------------------------------------------------
# Requirement 3: submit with mismatched job_id — no exception, no checkpoint
# ---------------------------------------------------------------------------

def test_loop_submit_mismatched_job_id_no_exception_no_checkpoint(tmp_path):
    """
    When submit_application is called with a job_id that differs from the
    reviewed job:
    - no exception is raised
    - the checkpoint is not called
    - the model receives an INVALID_ARGUMENTS error result
    - the run continues to the final answer
    """
    from agent.checkpoint import HumanApprovalCheckpoint
    from agent.logger import AgentLogger

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_job_posting",
            "arguments": {"url": "mock://jobs/job_001"},
        },
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Tailored CV",
                "job_id": "job_001",
                "kind": "cv",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Cover letter",
                "job_id": "job_001",
                "kind": "cover_letter",
            },
        },
        # Wrong job_id — does not match the loaded job ("job_001").
        {
            "type": "tool_call",
            "tool_name": "submit_application",
            "arguments": {
                "cv_path": "cv.txt",
                "cover_letter_path": "cl.txt",
                "job_id": "WRONG_JOB_ID",
            },
        },
        {
            "type": "final",
            "content": "Stopped: job ID mismatch.",
        },
    ])

    checkpoint = HumanApprovalCheckpoint(auto_approve=True)
    logger = AgentLogger(log_dir=tmp_path, run_id="mismatch_loop")
    agent = AgentLoop(model, logger=logger, checkpoint=checkpoint)

    # Must not raise.
    result = agent.run()

    assert result["stop_reason"] == "done"

    # Checkpoint was not called.
    assert checkpoint.last_decision is None

    # The model received INVALID_ARGUMENTS for the mismatched submit.
    submit_tool_msgs = [
        m for m in result["messages"]
        if m.get("role") == "tool" and m.get("name") == "submit_application"
    ]
    assert len(submit_tool_msgs) == 1
    assert '"INVALID_ARGUMENTS"' in submit_tool_msgs[0]["content"]


# ---------------------------------------------------------------------------
# Requirement 4: malformed model responses — each counts as a step, no crash
# ---------------------------------------------------------------------------

class _AlwaysReturnsModel:
    """Helper: returns the same response object every call."""
    def __init__(self, response):
        self._response = response

    def call_model(self, messages, tools):
        return self._response


def test_loop_non_dict_response_counts_as_step_ends_by_max_steps():
    """A model that always returns a non-dict: each counts as a step, run
    ends at max_steps without raising."""
    agent = AgentLoop(_AlwaysReturnsModel("not a dict"))
    result = agent.run()
    assert result["stop_reason"] == "max_steps"
    assert result["step_count"] == MAX_STEPS


def test_loop_unknown_response_type_counts_as_step_ends_by_max_steps():
    """A model that always returns an unknown type: each counts as a step,
    run ends at max_steps without raising."""
    agent = AgentLoop(_AlwaysReturnsModel({"type": "unsupported_xyz"}))
    result = agent.run()
    assert result["stop_reason"] == "max_steps"
    assert result["step_count"] == MAX_STEPS


def test_loop_non_dict_arguments_counts_as_step_ends_by_max_steps():
    """A model that always returns non-dict arguments: each counts as a step,
    run ends at max_steps without raising."""
    agent = AgentLoop(_AlwaysReturnsModel({
        "type": "tool_call",
        "tool_name": "read_master_cv",
        "arguments": "this is not a dict",
    }))
    result = agent.run()
    assert result["stop_reason"] == "max_steps"
    assert result["step_count"] == MAX_STEPS


# ---------------------------------------------------------------------------
# Requirement 5: usage passthrough — tokens, cost and totals in the log
# ---------------------------------------------------------------------------

def test_loop_usage_passthrough_to_log_with_prices(monkeypatch, tmp_path):
    """
    FakeModel responses with a 'usage' field produce:
    - tool_call log events with the correct tokens_in, tokens_out and cost_usd
      (computed from monkeypatched price constants)
    - a stop event with total_tokens_in, total_tokens_out, total_cost_usd and
      a non-zero total_duration_ms
    """
    from agent.checkpoint import HumanApprovalCheckpoint
    from agent.logger import AgentLogger

    # Patch prices so cost arithmetic is non-trivial.
    monkeypatch.setattr("agent.config.PRICE_PER_MTOK_INPUT", 1.0)
    monkeypatch.setattr("agent.config.PRICE_PER_MTOK_OUTPUT", 2.0)

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
            "usage": {"input_tokens": 100, "output_tokens": 50},
        },
        {
            "type": "final",
            "content": "Done.",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    ])

    logger = AgentLogger(log_dir=tmp_path, run_id="usage_prices")
    agent = AgentLoop(
        model,
        checkpoint=HumanApprovalCheckpoint(auto_approve=True),
        logger=logger,
    )
    agent.run()

    events = [
        json.loads(line)
        for line in (tmp_path / "usage_prices.jsonl")
            .read_text(encoding="utf-8").splitlines()
    ]

    tool_event = next(e for e in events if e["event"] == "tool_call")
    assert tool_event["tokens_in"] == 100
    assert tool_event["tokens_out"] == 50
    # cost = 100/1e6 * 1.0 + 50/1e6 * 2.0 = 2e-4
    assert tool_event["cost_usd"] == pytest.approx(2e-4)

    stop_event = next(e for e in events if e["event"] == "stop")
    # step totals (100) + final answer tokens (10) = 110 input
    assert stop_event["total_tokens_in"] == 110
    # 50 + 5 = 55 output
    assert stop_event["total_tokens_out"] == 55
    # 110/1e6 * 1.0 + 55/1e6 * 2.0 = 2.2e-4
    assert stop_event["total_cost_usd"] == pytest.approx(2.2e-4)
    assert stop_event["total_duration_ms"] > 0


# ---------------------------------------------------------------------------
# Requirement 6: checkpoint timeout — stop reason, no submit, log timed_out
# ---------------------------------------------------------------------------

def _slow_input_fn(_prompt):
    """Simulates a user who never responds within the timeout window."""
    time.sleep(10)
    return "yes"


def test_loop_checkpoint_timeout_stops_run_and_logs_timed_out(
    monkeypatch, tmp_path
):
    """
    When the interactive checkpoint times out (slow input_fn, 0.1 s timeout):
    - the run stops with stop_reason 'checkpoint_timeout'
    - submit_application is never executed via execute_tool
    - the human_checkpoint log event has timed_out == True
    """
    from agent.checkpoint import HumanApprovalCheckpoint
    from agent.logger import AgentLogger
    from agent.tools.registry import TOOL_FUNCTIONS

    executed = []

    def tracking_execute(tool_name, arguments):
        executed.append(tool_name)
        return TOOL_FUNCTIONS[tool_name](**arguments)

    monkeypatch.setattr("agent.loop.execute_tool", tracking_execute)

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_job_posting",
            "arguments": {"url": "mock://jobs/job_001"},
        },
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Tailored CV",
                "job_id": "job_001",
                "kind": "cv",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Cover letter",
                "job_id": "job_001",
                "kind": "cover_letter",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "submit_application",
            "arguments": {
                "cv_path": "sandbox/output/job_001_cv.txt",
                "cover_letter_path": "sandbox/output/job_001_cover_letter.txt",
                "job_id": "job_001",
            },
        },
    ])

    checkpoint = HumanApprovalCheckpoint(
        input_fn=_slow_input_fn,
        timeout_seconds=0.1,
    )
    logger = AgentLogger(log_dir=tmp_path, run_id="timeout_loop")
    agent = AgentLoop(model, logger=logger, checkpoint=checkpoint)

    result = agent.run()

    assert result["stop_reason"] == "checkpoint_timeout"

    # submit_application must never have been executed via execute_tool.
    assert "submit_application" not in executed

    # The log must record the checkpoint with timed_out == True.
    events = [
        json.loads(line)
        for line in (tmp_path / "timeout_loop.jsonl")
            .read_text(encoding="utf-8").splitlines()
    ]
    checkpoint_events = [e for e in events if e["event"] == "human_checkpoint"]
    assert len(checkpoint_events) == 1
    assert checkpoint_events[0]["timed_out"] is True
