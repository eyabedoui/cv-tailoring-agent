"""
Tests for agent/session.py: Session multi-turn chat wrapper.
"""

import pytest
from agent.fake_model import FakeModel
from agent.loop import AgentLoop
from agent.checkpoint import HumanApprovalCheckpoint
from agent.session import Session
from agent.config import MAX_STEPS_PER_SESSION, MAX_HISTORY_MESSAGES


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


class _ErrorModel:
    """Model that always raises ModelUnavailableError."""
    def call_model(self, messages, tools):
        from agent.model import ModelUnavailableError
        raise ModelUnavailableError("No credits available.")


# ---------------------------------------------------------------------------
# Two-turn conversation
# ---------------------------------------------------------------------------

def test_two_turn_session_returns_results():
    model = FakeModel([
        _resp("final", content="Done turn 1."),
        _resp("final", content="Done turn 2."),
    ])
    session = Session(model=model, checkpoint=_auto_cp())

    r1 = session.send("Task 1.")
    assert r1["stop_reason"] == "done"
    assert r1["answer"] == "Done turn 1."

    r2 = session.send("Task 2.")
    assert r2["stop_reason"] == "done"
    assert r2["answer"] == "Done turn 2."


def test_history_passed_to_second_turn(monkeypatch):
    captured = []
    original_run = AgentLoop.run

    def spy(self, initial_messages=None, state=None):
        captured.append(list(initial_messages or []))
        return original_run(self, initial_messages=initial_messages, state=state)

    monkeypatch.setattr(AgentLoop, "run", spy)

    model = FakeModel([
        _resp("final", content="R1."),
        _resp("final", content="R2."),
    ])
    session = Session(model=model, checkpoint=_auto_cp())

    session.send("First task.")
    session.send("Second task.")

    # First call: only the initial user message
    assert len(captured[0]) == 1
    assert captured[0][0]["content"] == "First task."

    # Second call: history from turn 1 + new user message
    assert len(captured[1]) > 1
    assert any(m["content"] == "Second task." for m in captured[1])


def test_step_count_accumulates_across_turns():
    model = FakeModel([
        _resp("tool_call", "read_master_cv"),
        _resp("final", content="R1."),
        _resp("tool_call", "read_master_cv"),
        _resp("final", content="R2."),
    ])
    session = Session(model=model, checkpoint=_auto_cp())
    session.send("Turn 1.")
    session.send("Turn 2.")
    assert session._total_steps == 2  # 1 tool call per turn


# ---------------------------------------------------------------------------
# History trimming
# ---------------------------------------------------------------------------

def test_history_trimmed_to_max():
    session = Session(model=FakeModel([]), checkpoint=_auto_cp())
    session._history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
        for i in range(MAX_HISTORY_MESSAGES + 10)
    ]
    session._trim_history()
    assert len(session._history) <= MAX_HISTORY_MESSAGES


def test_history_starts_with_user_after_trim():
    session = Session(model=FakeModel([]), checkpoint=_auto_cp())
    # Put a mix of roles, more than MAX, starting with assistant
    session._history = [
        {"role": "assistant" if i == 0 else ("user" if i % 2 == 1 else "assistant"),
         "content": f"msg {i}"}
        for i in range(MAX_HISTORY_MESSAGES + 5)
    ]
    session._trim_history()
    if session._history:
        assert session._history[0]["role"] == "user"


def test_trim_already_within_limit_is_no_op():
    session = Session(model=FakeModel([]), checkpoint=_auto_cp())
    history = [
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": "done"},
    ]
    session._history = list(history)
    session._trim_history()
    assert session._history == history


# ---------------------------------------------------------------------------
# Session step limit
# ---------------------------------------------------------------------------

def test_session_limit_returns_session_limit_stop_reason():
    session = Session(model=FakeModel([_resp("final")]), checkpoint=_auto_cp())
    session._total_steps = MAX_STEPS_PER_SESSION

    result = session.send("One more.")
    assert result["stop_reason"] == "session_limit"


def test_session_limit_does_not_call_run(monkeypatch):
    ran = []
    monkeypatch.setattr(AgentLoop, "run", lambda self, **kw: ran.append(True))

    session = Session(model=FakeModel([]), checkpoint=_auto_cp())
    session._total_steps = MAX_STEPS_PER_SESSION

    session.send("Task.")
    assert ran == []  # AgentLoop.run was never called


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def test_reset_clears_history_and_state():
    model = FakeModel([_resp("final")])
    session = Session(model=model, checkpoint=_auto_cp())
    session.send("Task.")

    assert session._history  # Non-empty after a run

    session.reset()
    assert session._history == []
    assert session._workflow_state is None
    assert session._total_steps == 0


def test_reset_allows_new_send():
    model = FakeModel([
        _resp("final", content="Before reset."),
        _resp("final", content="After reset."),
    ])
    session = Session(model=model, checkpoint=_auto_cp())
    session.send("Task 1.")
    session.reset()
    r = session.send("Task 2.")
    assert r["answer"] == "After reset."


# ---------------------------------------------------------------------------
# ModelUnavailableError handling
# ---------------------------------------------------------------------------

def test_model_unavailable_returns_model_unavailable_stop_reason():
    session = Session(model=_ErrorModel(), checkpoint=_auto_cp())
    result = session.send("Task.")
    assert result["stop_reason"] == "model_unavailable"


def test_model_unavailable_answer_contains_error_message():
    session = Session(model=_ErrorModel(), checkpoint=_auto_cp())
    result = session.send("Task.")
    assert "No credits available." in result["answer"]


def test_model_unavailable_does_not_update_history():
    session = Session(model=_ErrorModel(), checkpoint=_auto_cp())
    before = list(session._history)
    session.send("Task.")
    assert session._history == before  # History unchanged on failure


def test_model_unavailable_does_not_increment_steps():
    session = Session(model=_ErrorModel(), checkpoint=_auto_cp())
    session.send("Task.")
    assert session._total_steps == 0
