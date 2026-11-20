
"""A7: Maximum two CV revisions per application."""

from unittest.mock import patch

from agent.config import MAX_REVISIONS
from agent.errors import make_error
from agent.fake_model import FakeModel
from agent.loop import AgentLoop


def tool_call(job_id, text):
    return {
        "type": "tool_call",
        "tool_name": "save_tailored_cv",
        "arguments": {
            "text": text,
            "job_id": job_id,
            "kind": "cv",
        },
    }


def final():
    return {
        "type": "final",
        "content": "Done.",
    }


def run_saves(texts, state=None, side_effect=None, job_id="job_001"):
    responses = [
        tool_call(job_id, text)
        for text in texts
    ]
    responses.append(final())

    model = FakeModel(responses)

    if side_effect is None:
        side_effect = lambda name, args: {
            "path": f"cv_{args['job_id']}.md",
            "saved": True,
        }

    with patch(
        "agent.loop.execute_tool",
        side_effect=side_effect,
    ) as execute:
        result = AgentLoop(model=model).run(state=state)

    return result, execute.call_count


def test_initial_draft_does_not_count_as_revision():
    result, calls = run_saves(["Initial CV"])

    assert calls == 1
    assert result["state"]["revision_count"] == 0
    assert result["state"]["tailored_cv"] == "Initial CV"


def test_first_revision_allowed():
    initial, _ = run_saves(["Initial CV"])

    result, calls = run_saves(
        ["First revision"],
        state=initial["state"],
    )

    assert calls == 1
    assert result["state"]["revision_count"] == 1
    assert result["state"]["tailored_cv"] == "First revision"


def test_second_revision_allowed():
    initial, _ = run_saves(["Initial CV"])
    first, _ = run_saves(
        ["First revision"],
        state=initial["state"],
    )

    second, calls = run_saves(
        ["Second revision"],
        state=first["state"],
    )

    assert calls == 1
    assert second["state"]["revision_count"] == MAX_REVISIONS
    assert second["state"]["tailored_cv"] == "Second revision"


def test_third_revision_blocked():
    initial, _ = run_saves(["Initial CV"])
    first, _ = run_saves(
        ["First revision"],
        state=initial["state"],
    )
    second, _ = run_saves(
        ["Second revision"],
        state=first["state"],
    )

    third, calls = run_saves(
        ["Third revision"],
        state=second["state"],
    )

    assert calls == 0
    assert third["state"]["revision_count"] == MAX_REVISIONS
    assert third["state"]["tailored_cv"] == "Second revision"
    assert "Revision limit reached" in str(third["messages"])


def test_new_job_has_fresh_revision_limit():
    initial, _ = run_saves(["Initial CV"])
    first, _ = run_saves(
        ["First revision"],
        state=initial["state"],
    )
    second, _ = run_saves(
        ["Second revision"],
        state=first["state"],
    )

    new_job, calls = run_saves(
        ["New job initial CV"],
        state=second["state"],
        job_id="job_002",
    )

    assert calls == 1
    assert new_job["state"]["revision_count"] == 0
    assert new_job["state"]["revision_job_id"] == "job_002"


def test_failed_save_does_not_consume_revision():
    initial, _ = run_saves(["Initial CV"])

    def failing_save(name, args):
        return make_error(
            "PATH_NOT_ALLOWED",
            "Simulated save failure",
            retryable=False,
        )

    result, calls = run_saves(
        ["Failed revision"],
        state=initial["state"],
        side_effect=failing_save,
    )

    assert calls == 1
    assert result["state"]["revision_count"] == 0
    assert result["state"]["tailored_cv"] == "Initial CV"
