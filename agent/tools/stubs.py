
"""
Temporary stub implementations of the six CV-tailoring tools.

These functions simulate the expected tool behavior.
Person B can later replace them with real implementations
while keeping the same tool contracts.
"""

from agent.errors import make_error, INVALID_ARGUMENTS


def read_job_posting(url: str) -> dict:
    """Simulate reading a job posting."""

    return {
        "job_id": "job_001",
        "title": "Junior AI Engineer",
        "company": "Example Company",
        "requirements": [
            "Python programming",
            "Machine learning",
            "Data analysis",
            "Problem solving",
        ],
        "text": (
            "We are looking for a Junior AI Engineer with "
            "Python, machine learning and data analysis skills."
        ),
    }


def read_master_cv() -> dict:
    """Return a sample master CV."""

    cv_text = (
        "Software Engineering Student\n"
        "Skills: Python, C++, JavaScript, SQL\n"
        "Experience: AI Engineering Internship\n"
        "Education: Software Engineering Degree\n"
    )

    return {
        "text": cv_text,
        "sections": {
            "education": "Software Engineering Degree",
            "skills": ["Python", "C++", "JavaScript", "SQL"],
            "experience": ["AI Engineering Internship"],
        },
    }


def match_skills(cv_text: str, job: dict) -> dict:
    """Simulate matching CV skills against job requirements."""

    return {
        "matched": ["Python programming", "Problem solving"],
        "missing": ["Machine learning", "Data analysis"],
        "score": 0.5,
    }


def check_format(cv_text: str) -> dict:
    """Simulate checking the CV format."""

    return {
        "ok": True,
        "issues": [],
    }


def save_tailored_cv(text: str, job_id: str, kind: str) -> dict:
    """Simulate saving a tailored CV or cover letter."""

    if kind not in ("cv", "cover_letter"):
        return make_error(
            INVALID_ARGUMENTS,
            f"kind must be 'cv' or 'cover_letter', got {kind!r}",
        )

    return {
        "path": f"sandbox/output/{job_id}_{kind}.txt",
        "saved": True,
    }


def submit_application(
    cv_path: str,
    cover_letter_path: str,
    job_id: str,
) -> dict:
    """
    Simulate submitting an application.

    This is only a stub. The real agent must enforce
    human approval before calling this tool.
    """

    return {
        "status": "submitted",
        "application_id": f"app_{job_id}",
    }
