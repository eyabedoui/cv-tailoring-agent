"""
Tests for AgentLoop: state carry-over, "state" key in all returns, on_step callback.
"""

import pytest
from agent.fake_model import FakeModel
from agent.loop import AgentLoop
from agent.checkpoint import HumanApprovalCheckpoint
from agent.config import MAX_STEPS


def _auto_cp():
    return HumanApprovalCheckpoint(auto_approve=True)


def _resp(type_, tool_name=None, arguments=None, content="Done."):
    if type_ == "final":
        return {"type": "final", "content": content, "usage": {"input_tokens": 1, "output_tokens": 1}}
    return {
        "type": "tool_call",
        "tool_name": tool_name,
        "arguments": arguments or {},
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


# ---------------------------------------------------------------------------
# "state" key present on every return path
# ---------------------------------------------------------------------------

def test_final_result_has_state_key():
    agent = AgentLoop(model=FakeModel([_resp("final")]), checkpoint=_auto_cp())
    result = agent.run(initial_messages=[{"role": "user", "content": "Task."}])
    assert "state" in result


def test_state_has_four_workflow_keys():
    agent = AgentLoop(model=FakeModel([_resp("final")]), checkpoint=_auto_cp())
    result = agent.run(initial_messages=[{"role": "user", "content": "Task."}])
    for key in ("job", "master_cv", "tailored_cv", "cover_letter"):
        assert key in result["state"]


def test_max_steps_result_has_state():
    # Alternate between two tools so identical_call_count never fires first.
    tools = ["read_master_cv", "check_format"]
    responses = [_resp("tool_call", tools[i % 2]) for i in range(MAX_STEPS + 1)]
    agent = AgentLoop(model=FakeModel(responses), checkpoint=_auto_cp())
    result = agent.run(initial_messages=[{"role": "user", "content": "Task."}])
    assert result["stop_reason"] == "max_steps"
    assert "state" in result


def test_user_rejected_result_has_state():
    # Build a model that provides all prerequisites then submits.
    job = {"job_id": "job_001", "title": "Engineer", "company": "ACME",
           "requirements": [], "text": ""}
    responses = [_resp("final")]
    cp = HumanApprovalCheckpoint(auto_reject=True)
    state = {
        "job": job,
        "master_cv": "My CV",
        "tailored_cv": "Tailored",
        "cover_letter": "Letter",
    }
    responses = [
        _resp("tool_call", "submit_application",
              {"cv_path": "sandbox/output/cv_job_001.md",
               "cover_letter_path": "sandbox/output/cover_letter_job_001.md",
               "job_id": "job_001"}),
    ]
    agent = AgentLoop(model=FakeModel(responses), checkpoint=cp)
    result = agent.run(
        initial_messages=[{"role": "user", "content": "Task."}],
        state=state,
    )
    assert result["stop_reason"] == "user_rejected"
    assert "state" in result


# ---------------------------------------------------------------------------
# State carry-over via state= parameter
# ---------------------------------------------------------------------------

def test_state_param_initialises_job():
    initial_state = {
        "job": {"job_id": "job_001", "title": "Engineer", "company": "ACME",
                "requirements": [], "text": ""},
        "master_cv": "My CV",
        "tailored_cv": None,
        "cover_letter": None,
    }
    agent = AgentLoop(model=FakeModel([_resp("final")]), checkpoint=_auto_cp())
    result = agent.run(
        initial_messages=[{"role": "user", "content": "Task."}],
        state=initial_state,
    )
    assert result["state"]["job"]["job_id"] == "job_001"
    assert result["state"]["master_cv"] == "My CV"


def test_state_none_gives_none_values():
    agent = AgentLoop(model=FakeModel([_resp("final")]), checkpoint=_auto_cp())
    result = agent.run(initial_messages=[{"role": "user", "content": "Task."}])
    assert result["state"]["job"] is None
    assert result["state"]["master_cv"] is None
    assert result["state"]["tailored_cv"] is None
    assert result["state"]["cover_letter"] is None


def test_state_per_turn_counters_always_fresh():
    # Provide a state that looks like a nearly-exhausted run; the new run
    # should start with step_count = 0 (not carry loop control counters).
    # We verify by checking step_count in the result — it should count only
    # the steps taken in this run, not any prior run.
    agent = AgentLoop(
        model=FakeModel([_resp("tool_call", "read_master_cv"), _resp("final")]),
        checkpoint=_auto_cp(),
    )
    result = agent.run(
        initial_messages=[{"role": "user", "content": "Task."}],
        state={"job": None, "master_cv": "CV", "tailored_cv": None, "cover_letter": None},
    )
    assert result["step_count"] == 1  # Only the tool call in this run counts


# ---------------------------------------------------------------------------
# on_step callback
# ---------------------------------------------------------------------------

def test_on_step_called_after_tool_execution():
    events = []
    agent = AgentLoop(
        model=FakeModel([_resp("tool_call", "read_master_cv"), _resp("final")]),
        checkpoint=_auto_cp(),
        on_step=events.append,
    )
    agent.run(initial_messages=[{"role": "user", "content": "Task."}])
    assert len(events) == 1
    ev = events[0]
    assert ev["tool"] == "read_master_cv"
    assert "step" in ev
    assert "arguments" in ev
    assert "result" in ev


def test_on_step_not_called_for_final_answer():
    events = []
    agent = AgentLoop(
        model=FakeModel([_resp("final")]),
        checkpoint=_auto_cp(),
        on_step=events.append,
    )
    agent.run(initial_messages=[{"role": "user", "content": "Task."}])
    assert events == []


def test_on_step_failing_callback_does_not_crash_run():
    def bad_callback(event):
        raise RuntimeError("callback exploded")

    agent = AgentLoop(
        model=FakeModel([_resp("tool_call", "read_master_cv"), _resp("final")]),
        checkpoint=_auto_cp(),
        on_step=bad_callback,
    )
    result = agent.run(initial_messages=[{"role": "user", "content": "Task."}])
    assert result["stop_reason"] == "done"


def test_on_step_called_for_checkpoint():
    job = {"job_id": "job_001", "title": "Engineer", "company": "ACME",
           "requirements": [], "text": ""}
    state = {
        "job": job, "master_cv": "CV", "tailored_cv": "TCV", "cover_letter": "CL",
    }
    responses = [
        _resp("tool_call", "submit_application",
              {"cv_path": "sandbox/output/cv_job_001.md",
               "cover_letter_path": "sandbox/output/cover_letter_job_001.md",
               "job_id": "job_001"}),
        _resp("final"),
    ]
    events = []
    agent = AgentLoop(
        model=FakeModel(responses),
        checkpoint=HumanApprovalCheckpoint(auto_approve=True),
        on_step=events.append,
    )
    agent.run(initial_messages=[{"role": "user", "content": "Task."}], state=state)
    checkpoint_events = [e for e in events if e["tool"] == "human_checkpoint"]
    assert len(checkpoint_events) == 1
    assert "approved" in checkpoint_events[0]["result"]
    assert "timed_out" in checkpoint_events[0]["result"]
