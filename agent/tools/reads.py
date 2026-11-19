"""
Real implementations of the four read tools:
read_job_posting, read_master_cv, match_skills, check_format.

Each function accepts optional injection parameters for test isolation;
when called through execute_tool those parameters are absent and the
module-level defaults (pointing to sandbox/) are used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.config import SANDBOX_DIR
from agent.errors import make_error, NOT_FOUND, EMPTY_POSTING, SITE_NOT_ALLOWED

# ---------------------------------------------------------------------------
# Module-level defaults — replace via monkeypatch in tests
# ---------------------------------------------------------------------------

_client_instance = None
_cv_path: Path | None = None


def _get_client():
    global _client_instance
    if _client_instance is None:
        from agent.tools.clients import FakePostingClient
        _client_instance = FakePostingClient()
    return _client_instance


def _get_cv_path() -> Path:
    global _cv_path
    if _cv_path is None:
        _cv_path = Path(SANDBOX_DIR) / "master_cv.md"
    return _cv_path


# ---------------------------------------------------------------------------
# Skill aliases: map a lowercase requirement to alternative phrasings.
# ---------------------------------------------------------------------------

_SKILL_ALIASES: dict[str, list[str]] = {
    "javascript": ["js"],
    "typescript": ["ts"],
    "unit testing": ["pytest", "jest", "unittest", "mocha", "jasmine"],
    "version control": ["git", "svn"],
    "data analysis": ["data analytics", "pandas"],
    "machine learning": ["scikit-learn", "sklearn"],
    "natural language processing": ["nlp"],
    "rest api": ["rest apis", "restful"],
    "rest apis": ["rest api", "restful"],
    "continuous integration": ["ci/cd", "github actions", "jenkins"],
    "node.js": ["nodejs", "node js"],
    "html/css": ["html", "css"],
    "problem solving": ["problem-solving"],
    "communication": ["written and verbal communication", "verbal communication"],
}


# ---------------------------------------------------------------------------
# read_job_posting
# ---------------------------------------------------------------------------

def read_job_posting(url: str, _client=None) -> dict:
    """Fetch a job posting by URL and return its structured data."""
    # Defense-in-depth: re-check allowlist for http/https URLs that reach here
    # (the registry pre-check is the primary gate).
    if url.lower().startswith(("http://", "https://")):
        from agent.sites import is_url_allowed, is_own_url, site_names
        if not is_url_allowed(url) and not is_own_url(url):
            names = ", ".join(sorted(site_names()))
            return make_error(
                SITE_NOT_ALLOWED,
                f"URL is not from an allowed site. Allowed sites: {names}.",
            )

    client = _client if _client is not None else _get_client()
    result = client.fetch(url)

    if "error" in result:
        return result

    # _posting is set by FakePostingClient; W4 will add parse_posting for real markdown.
    posting = result.get("_posting")
    if posting is None:
        return make_error(NOT_FOUND, f"Cannot parse posting from URL {url!r}")

    if not posting.get("text", "").strip():
        return make_error(EMPTY_POSTING, f"Job posting {posting.get('job_id', url)!r} has no descriptive text")

    return {
        "job_id": posting["job_id"],
        "title": posting["title"],
        "company": posting["company"],
        "requirements": posting["requirements"],
        "text": posting["text"],
    }


# ---------------------------------------------------------------------------
# read_master_cv
# ---------------------------------------------------------------------------

def read_master_cv(_cv_path: Path | None = None) -> dict:
    """Read and parse the candidate's master CV from the sandbox."""
    cv_path = _cv_path if _cv_path is not None else _get_cv_path()

    if not cv_path.exists():
        return make_error(NOT_FOUND, f"Master CV not found at {cv_path!r}")

    text = cv_path.read_text(encoding="utf-8")
    sections = _parse_cv_sections(text)
    return {"text": text, "sections": sections}


def _parse_cv_sections(text: str) -> dict[str, Any]:
    """Split a markdown CV into sections keyed by lowercase heading name."""
    sections: dict[str, Any] = {}
    current: str | None = None
    buf: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip().lower()
            buf = []
        elif line.startswith("# "):
            pass  # skip top-level title
        else:
            if current is not None:
                buf.append(line)

    if current is not None:
        sections[current] = "\n".join(buf).strip()

    return sections


# ---------------------------------------------------------------------------
# match_skills
# ---------------------------------------------------------------------------

def match_skills(cv_text: str, job: dict) -> dict:
    """
    Compare job requirements against the CV text.

    Uses case-insensitive substring matching with a small alias table so
    that, e.g., "unit testing" matches a CV that mentions "pytest".
    """
    requirements: list[str] = job.get("requirements", [])
    if not requirements:
        return {"matched": [], "missing": [], "score": 0.0}

    cv_lower = cv_text.lower()
    matched: list[str] = []
    missing: list[str] = []

    for req in requirements:
        if _skill_present(req.lower(), cv_lower):
            matched.append(req)
        else:
            missing.append(req)

    score = round(len(matched) / len(requirements), 4)
    return {"matched": matched, "missing": missing, "score": score}


def _skill_present(req_lower: str, cv_lower: str) -> bool:
    if req_lower in cv_lower:
        return True
    for alias in _SKILL_ALIASES.get(req_lower, []):
        if alias.lower() in cv_lower:
            return True
    return False


# ---------------------------------------------------------------------------
# check_format
# ---------------------------------------------------------------------------

def check_format(cv_text: str) -> dict:
    """
    Check the CV for basic formatting issues.

    Currently flags only lines that exceed 160 characters.
    Returns ok=True with an empty issues list when no problems are found.
    """
    issues: list[str] = []
    for i, line in enumerate(cv_text.splitlines(), start=1):
        if len(line) > 160:
            issues.append(f"Line {i} exceeds 160 characters ({len(line)} chars)")
    return {"ok": len(issues) == 0, "issues": issues}
