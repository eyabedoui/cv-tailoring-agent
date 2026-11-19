"""
Tests for submit_application input validation and browser-reconciliation logic
(audit item 2).

Coverage:
- Missing CV file → INVALID_ARGUMENTS
- Missing cover-letter file → INVALID_ARGUMENTS
- Absolute path → PATH_NOT_ALLOWED
- Path traversal (..) → PATH_NOT_ALLOWED
- Invalid job_id format → INVALID_ARGUMENTS
- Browser not called when validation fails
- Portal state before / after browser submit
- Browser claims success but portal has no record → BAD_RESPONSE
- Browser reports failure but portal already has record → success
- Timeout / step-limit reported by browser client → passes through
- Duplicate submit via browser path
"""

from pathlib import Path

import pytest

from agent.tools.writes import submit_application
from sandbox.portal import Portal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _portal(tmp_path: Path) -> Portal:
    return Portal(sandbox_dir=str(tmp_path))


def _make_files(portal: Portal, job_id: str) -> tuple[str, str]:
    cv = f"cv_{job_id}.md"
    cl = f"cover_letter_{job_id}.md"
    (portal.output_dir / cv).write_text("CV text", encoding="utf-8")
    (portal.output_dir / cl).write_text("CL text", encoding="utf-8")
    return cv, cl


class _FakeSubmitClient:
    def __init__(self, response: dict):
        self._response = response
        self.calls: list[tuple[str, str]] = []

    def submit(self, job_id: str, apply_url: str) -> dict:
        self.calls.append((job_id, apply_url))
        return self._response


# ---------------------------------------------------------------------------
# File existence validation
# ---------------------------------------------------------------------------

def test_missing_cv_returns_invalid_arguments(tmp_path):
    portal = _portal(tmp_path)
    (portal.output_dir / "cover_letter_job_001.md").write_text("CL", encoding="utf-8")
    result = submit_application("cv_job_001.md", "cover_letter_job_001.md", "job_001", _portal=portal)
    assert result["error"] == "INVALID_ARGUMENTS"
    assert "cv_path" in result["message"]


def test_missing_cover_letter_returns_invalid_arguments(tmp_path):
    portal = _portal(tmp_path)
    (portal.output_dir / "cv_job_001.md").write_text("CV", encoding="utf-8")
    result = submit_application("cv_job_001.md", "cover_letter_job_001.md", "job_001", _portal=portal)
    assert result["error"] == "INVALID_ARGUMENTS"
    assert "cover_letter_path" in result["message"]


def test_missing_both_files_reports_cv_first(tmp_path):
    portal = _portal(tmp_path)
    result = submit_application("cv_job_001.md", "cover_letter_job_001.md", "job_001", _portal=portal)
    assert result["error"] == "INVALID_ARGUMENTS"


# ---------------------------------------------------------------------------
# Path safety validation (fires before file existence check)
# ---------------------------------------------------------------------------

def test_absolute_cv_path_rejected(tmp_path):
    result = submit_application("/etc/cv.md", "cl.md", "job_001", _portal=_portal(tmp_path))
    assert result["error"] == "PATH_NOT_ALLOWED"


def test_absolute_cl_path_rejected(tmp_path):
    result = submit_application("cv.md", "/tmp/cl.md", "job_001", _portal=_portal(tmp_path))
    assert result["error"] == "PATH_NOT_ALLOWED"


def test_traversal_in_cv_path_rejected(tmp_path):
    result = submit_application("../secret.md", "cl.md", "job_001", _portal=_portal(tmp_path))
    assert result["error"] == "PATH_NOT_ALLOWED"


def test_traversal_in_cl_path_rejected(tmp_path):
    result = submit_application("cv.md", "../../cl.md", "job_001", _portal=_portal(tmp_path))
    assert result["error"] == "PATH_NOT_ALLOWED"


# ---------------------------------------------------------------------------
# Job ID validation
# ---------------------------------------------------------------------------

def test_invalid_job_id_returns_invalid_arguments(tmp_path):
    portal = _portal(tmp_path)
    result = submit_application("cv.md", "cl.md", "not-a-valid-id", _portal=portal)
    assert result["error"] == "INVALID_ARGUMENTS"
    assert "job_id" in result["message"]


def test_valid_live_site_job_id_passes_format_check(tmp_path):
    portal = _portal(tmp_path)
    cv = "cv_keejob-aabb1122.md"
    cl = "cover_letter_keejob-aabb1122.md"
    (portal.output_dir / cv).write_text("CV", encoding="utf-8")
    (portal.output_dir / cl).write_text("CL", encoding="utf-8")
    result = submit_application(cv, cl, "keejob-aabb1122", _portal=portal)
    assert result["status"] == "submitted"


# ---------------------------------------------------------------------------
# Browser not called when validation fails
# ---------------------------------------------------------------------------

def test_browser_not_called_when_cv_missing(tmp_path):
    portal = _portal(tmp_path)
    client = _FakeSubmitClient({"status": "submitted", "application_id": "x"})
    submit_application("cv_job_001.md", "cover_letter_job_001.md", "job_001",
                       _portal=portal, _submit_client=client)
    assert client.calls == [], "browser client must not be called when files are missing"


def test_browser_not_called_when_job_id_invalid(tmp_path):
    portal = _portal(tmp_path)
    client = _FakeSubmitClient({"status": "submitted", "application_id": "x"})
    submit_application("cv.md", "cl.md", "INVALID", _portal=portal, _submit_client=client)
    assert client.calls == [], "browser client must not be called when job_id is invalid"


def test_browser_not_called_when_path_traversal(tmp_path):
    portal = _portal(tmp_path)
    client = _FakeSubmitClient({"status": "submitted", "application_id": "x"})
    submit_application("../cv.md", "cl.md", "job_001", _portal=portal, _submit_client=client)
    assert client.calls == [], "browser client must not be called when path traversal detected"


# ---------------------------------------------------------------------------
# Portal state before / after browser submit
# ---------------------------------------------------------------------------

def test_portal_empty_before_submit(tmp_path):
    portal = _portal(tmp_path)
    assert not portal.has_applied("job_001")


def test_portal_has_record_after_successful_browser_submit(tmp_path):
    portal = _portal(tmp_path)
    cv, cl = _make_files(portal, "job_001")
    # Simulate Flask server recording the application
    portal.record_application("job_001", cv, cl)
    client = _FakeSubmitClient({"status": "submitted", "application_id": "app_job_001"})
    result = submit_application(cv, cl, "job_001", _portal=portal, _submit_client=client)
    assert result["status"] == "submitted"
    assert portal.has_applied("job_001")


# ---------------------------------------------------------------------------
# Browser ↔ portal reconciliation
# ---------------------------------------------------------------------------

def test_browser_success_no_portal_record_returns_bad_response(tmp_path):
    """Browser claims submitted, but portal has no record → BAD_RESPONSE."""
    portal = _portal(tmp_path)
    cv, cl = _make_files(portal, "job_001")
    # Portal is empty — browser "lied"
    client = _FakeSubmitClient({"status": "submitted", "application_id": "app_job_001"})
    result = submit_application(cv, cl, "job_001", _portal=portal, _submit_client=client)
    assert result["error"] == "BAD_RESPONSE"


def test_browser_failure_but_portal_has_record_returns_success(tmp_path):
    """Browser reports failure, but portal already recorded it → treat as success."""
    from agent.errors import make_error, PORTAL_DOWN
    portal = _portal(tmp_path)
    cv, cl = _make_files(portal, "job_001")
    # Pre-populate portal (Flask processed POST before browser timed out)
    portal.record_application("job_001", cv, cl)
    client = _FakeSubmitClient(make_error(PORTAL_DOWN, "browser navigation timed out"))
    result = submit_application(cv, cl, "job_001", _portal=portal, _submit_client=client)
    assert result["status"] == "submitted"
    assert result["application_id"] == "app_job_001"


def test_browser_portal_down_no_record_propagates_error(tmp_path):
    """Browser reports failure and portal has no record → return the error."""
    from agent.errors import make_error, PORTAL_DOWN
    portal = _portal(tmp_path)
    cv, cl = _make_files(portal, "job_001")
    client = _FakeSubmitClient(make_error(PORTAL_DOWN, "server unavailable"))
    result = submit_application(cv, cl, "job_001", _portal=portal, _submit_client=client)
    assert result["error"] == "PORTAL_DOWN"


# ---------------------------------------------------------------------------
# Timeout / step-limit pass-through
# ---------------------------------------------------------------------------

def test_timeout_error_passthrough(tmp_path):
    from agent.errors import make_error, TIMEOUT
    portal = _portal(tmp_path)
    cv, cl = _make_files(portal, "job_001")
    client = _FakeSubmitClient(make_error(TIMEOUT, "browser step limit reached", retryable=True))
    result = submit_application(cv, cl, "job_001", _portal=portal, _submit_client=client)
    assert result["error"] == "TIMEOUT"


# ---------------------------------------------------------------------------
# Duplicate via browser path
# ---------------------------------------------------------------------------

def test_duplicate_in_browser_path_via_portal_reconciliation(tmp_path):
    """Second browser submit: portal already has record, browser fails → still success."""
    from agent.errors import make_error, PORTAL_DOWN
    portal = _portal(tmp_path)
    cv, cl = _make_files(portal, "job_001")
    portal.record_application("job_001", cv, cl)

    # First attempt via browser — succeeds (reconcile: has record, browser success)
    client_ok = _FakeSubmitClient({"status": "submitted", "application_id": "app_job_001"})
    r1 = submit_application(cv, cl, "job_001", _portal=portal, _submit_client=client_ok)
    assert r1["status"] == "submitted"

    # Second attempt via browser — browser fails, but portal record still exists
    client_fail = _FakeSubmitClient(make_error(PORTAL_DOWN, "already processed"))
    r2 = submit_application(cv, cl, "job_001", _portal=portal, _submit_client=client_fail)
    assert r2["status"] == "submitted"
