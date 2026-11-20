"""A7: Human rejection must never create a portal application."""

from unittest.mock import patch

from agent.checkpoint import HumanApprovalCheckpoint
from agent.fake_model import FakeModel
from agent.loop import AgentLoop
from sandbox.portal import Portal


def test_human_rejection_leaves_portal_empty(tmp_path):
    """Rejecting at the checkpoint must not execute submission."""

    # Create an isolated fictional portal.
    portal = Portal(sandbox_dir=str(tmp_path))

    job = {
        "job_id": "job_001",
        "title": "Junior AI Engineer",
        "company": "Example Company",
        "requirements": ["Python"],
        "text": "Develop AI solutions.",
    }

    state = {
        "job": job,
        "master_cv": "Software Engineering Student\nSkills: Python",
        "tailored_cv": "Software Engineering Student\nSkills: Python",
        "cover_letter": "Dear Hiring Manager, I am applying.",
    }

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "submit_application",
            "arguments": {
                "cv_path": "cv_job_001.md",
                "cover_letter_path": "cover_letter_job_001.md",
                "job_id": "job_001",
            },
        },
    ])

    checkpoint = HumanApprovalCheckpoint(auto_reject=True)

    # Monitor the submission tool to ensure it is never called.
    with patch("agent.loop.execute_tool") as execute:
        result = AgentLoop(
            model=model,
            checkpoint=checkpoint,
        ).run(state=state)

    # The candidate's rejection must stop the workflow.
    assert result["stop_reason"] == "user_rejected"

    # No application submission should be attempted.
    execute.assert_not_called()

    # The fictional portal must contain no application record.
    assert portal.has_applied("job_001") is False
    assert not portal.applications_file.exists()