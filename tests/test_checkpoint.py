
import time
import threading
import pytest

from agent.checkpoint import HumanApprovalCheckpoint
from agent.fake_model import FakeModel
from agent.loop import AgentLoop
from agent.logger import AgentLogger


MASTER_CV = """Software Engineering Student
Skills: Python, C++, JavaScript
Experience: AI Internship
"""

TAILORED_CV = """Software Engineering Student
Skills: Python, C++, JavaScript, SQL
Experience: AI Internship
"""

COVER_LETTER = "Dear Hiring Manager, I am interested in this position."


def test_review_contains_job_information():
    checkpoint = HumanApprovalCheckpoint(auto_approve=True)

    review = checkpoint.build_review_text(
        job_title="Junior AI Engineer",
        company="Example Company",
        job_id="job_001",
        master_cv=MASTER_CV,
        tailored_cv=TAILORED_CV,
        cover_letter=COVER_LETTER,
    )

    assert "Junior AI Engineer" in review
    assert "Example Company" in review
    assert "job_001" in review


def test_review_contains_cv_diff_and_changes():
    checkpoint = HumanApprovalCheckpoint(auto_approve=True)

    review = checkpoint.build_review_text(
        job_title="Junior AI Engineer",
        company="Example Company",
        job_id="job_001",
        master_cv=MASTER_CV,
        tailored_cv=TAILORED_CV,
        cover_letter=COVER_LETTER,
    )

    assert "+Skills: Python, C++, JavaScript, SQL" in review
    assert "-Skills: Python, C++, JavaScript" in review
    assert "ADDED LINES" in review
    assert "REMOVED LINES" in review


def test_review_contains_cover_letter_and_exact_question():
    checkpoint = HumanApprovalCheckpoint(auto_approve=True)

    review = checkpoint.build_review_text(
        job_title="Junior AI Engineer",
        company="Example Company",
        job_id="job_001",
        master_cv=MASTER_CV,
        tailored_cv=TAILORED_CV,
        cover_letter=COVER_LETTER,
    )

    assert COVER_LETTER in review
    assert "Submit these files to job job_001?" in review


def test_auto_approve_returns_true():
    checkpoint = HumanApprovalCheckpoint(auto_approve=True)

    result = checkpoint.request_approval(
        "AI Engineer",
        "Example Company",
        "job_001",
        MASTER_CV,
        TAILORED_CV,
        COVER_LETTER,
    )

    assert result is True


def test_auto_reject_returns_false():
    checkpoint = HumanApprovalCheckpoint(auto_reject=True)

    result = checkpoint.request_approval(
        "AI Engineer",
        "Example Company",
        "job_001",
        MASTER_CV,
        TAILORED_CV,
        COVER_LETTER,
    )

    assert result is False


def test_scripted_decisions():
    checkpoint = HumanApprovalCheckpoint(
        scripted_decisions=[False, True]
    )

    first = checkpoint.request_approval(
        "AI Engineer",
        "Example Company",
        "job_001",
        MASTER_CV,
        TAILORED_CV,
        COVER_LETTER,
    )

    second = checkpoint.request_approval(
        "AI Engineer",
        "Example Company",
        "job_001",
        MASTER_CV,
        TAILORED_CV,
        COVER_LETTER,
    )

    assert first is False
    assert second is True


def test_interactive_approval():
    checkpoint = HumanApprovalCheckpoint(
        input_fn=lambda _: "yes"
    )

    result = checkpoint.request_approval(
        "AI Engineer",
        "Example Company",
        "job_001",
        MASTER_CV,
        TAILORED_CV,
        COVER_LETTER,
    )

    assert result is True


def test_auto_approve_and_reject_cannot_both_be_enabled():
    with pytest.raises(ValueError):
        HumanApprovalCheckpoint(
            auto_approve=True,
            auto_reject=True,
        )


def test_scripted_decisions_must_be_boolean():
    checkpoint = HumanApprovalCheckpoint(
        scripted_decisions=["yes"]
    )

    with pytest.raises(ValueError):
        checkpoint.request_approval(
            "AI Engineer",
            "Example Company",
            "job_001",
            MASTER_CV,
            TAILORED_CV,
            COVER_LETTER,
        )


# ---------------------------------------------------------------------------
# Item 5: checkpoint timeout
# ---------------------------------------------------------------------------

def _slow_input(_prompt):
    """Simulates a user who never responds."""
    time.sleep(10)
    return "yes"


def test_timeout_treats_as_rejected():
    checkpoint = HumanApprovalCheckpoint(
        input_fn=_slow_input,
        timeout_seconds=0.1,
    )

    result = checkpoint.request_approval(
        "AI Engineer", "Example Company", "job_001",
        MASTER_CV, TAILORED_CV, COVER_LETTER,
    )

    assert result is False
    assert checkpoint.timed_out is True
    assert checkpoint.last_decision is False


def test_timeout_does_not_submit(tmp_path):
    """When interactive input times out the loop returns checkpoint_timeout."""

    model = FakeModel([
        {"type": "tool_call", "tool_name": "read_job_posting",
         "arguments": {"url": "mock://jobs/job_001"}},
        {"type": "tool_call", "tool_name": "read_master_cv", "arguments": {}},
        {"type": "tool_call", "tool_name": "save_tailored_cv",
         "arguments": {"text": "cv", "job_id": "job_001", "kind": "cv"}},
        {"type": "tool_call", "tool_name": "save_tailored_cv",
         "arguments": {"text": "cl", "job_id": "job_001", "kind": "cover_letter"}},
        {"type": "tool_call", "tool_name": "submit_application",
         "arguments": {"cv_path": "x", "cover_letter_path": "y", "job_id": "job_001"}},
    ])

    executed = []

    def tracking_execute(tool_name, arguments):
        executed.append(tool_name)
        from agent.tools.registry import TOOL_FUNCTIONS
        return TOOL_FUNCTIONS[tool_name](**arguments)

    import agent.loop as loop_module
    original = loop_module.execute_tool

    checkpoint = HumanApprovalCheckpoint(
        input_fn=_slow_input,
        timeout_seconds=0.1,
    )
    logger = AgentLogger(log_dir=tmp_path, run_id="timeout_test")

    import unittest.mock as mock
    with mock.patch("agent.loop.execute_tool", side_effect=tracking_execute):
        agent = AgentLoop(model, checkpoint=checkpoint, logger=logger)
        result = agent.run()

    assert result["stop_reason"] == "checkpoint_timeout"
    assert "submit_application" not in executed


def test_auto_approve_ignores_timeout():
    """Auto-approve mode must not be affected by the timeout parameter."""
    checkpoint = HumanApprovalCheckpoint(
        auto_approve=True,
        timeout_seconds=0.001,  # would fire instantly if used
    )

    result = checkpoint.request_approval(
        "AI Engineer", "Example Company", "job_001",
        MASTER_CV, TAILORED_CV, COVER_LETTER,
    )

    assert result is True
    assert checkpoint.timed_out is False


def test_auto_reject_ignores_timeout():
    checkpoint = HumanApprovalCheckpoint(
        auto_reject=True,
        timeout_seconds=0.001,
    )

    result = checkpoint.request_approval(
        "AI Engineer", "Example Company", "job_001",
        MASTER_CV, TAILORED_CV, COVER_LETTER,
    )

    assert result is False
    assert checkpoint.timed_out is False


def test_scripted_mode_ignores_timeout():
    checkpoint = HumanApprovalCheckpoint(
        scripted_decisions=[True],
        timeout_seconds=0.001,
    )

    result = checkpoint.request_approval(
        "AI Engineer", "Example Company", "job_001",
        MASTER_CV, TAILORED_CV, COVER_LETTER,
    )

    assert result is True
    assert checkpoint.timed_out is False


def test_checkpoint_timeout_stop_reason_in_stop_rule():
    from agent.stop_rule import should_stop

    state = {
        "step_count": 3,
        "checkpoint_timed_out": True,
    }
    stop, reason = should_stop(state)
    assert stop is True
    assert reason == "checkpoint_timeout"
