
import pytest

from agent.checkpoint import HumanApprovalCheckpoint


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
