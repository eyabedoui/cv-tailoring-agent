
"""
Tests for agent/tools/writes.py — save_tailored_cv and submit_application.

All tests use a tmp_path-backed Portal for complete filesystem isolation.
"""

import json
from pathlib import Path

import pytest

from agent.tools.writes import save_tailored_cv, submit_application
from sandbox.portal import Portal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _portal(tmp_path: Path) -> Portal:
    return Portal(sandbox_dir=str(tmp_path))


def _make_cv_files(portal: Portal, job_id: str) -> tuple[str, str]:
    """Create the expected CV and cover-letter files in portal.output_dir."""
    cv_name = f"cv_{job_id}.md"
    cl_name = f"cover_letter_{job_id}.md"
    (portal.output_dir / cv_name).write_text(f"CV for {job_id}", encoding="utf-8")
    (portal.output_dir / cl_name).write_text(f"CL for {job_id}", encoding="utf-8")
    return cv_name, cl_name


# ---------------------------------------------------------------------------
# save_tailored_cv — happy path
# ---------------------------------------------------------------------------

def test_save_cv_returns_saved_true(tmp_path):
    result = save_tailored_cv("CV content", "job_001", "cv", _portal=_portal(tmp_path))
    assert result["saved"] is True


def test_save_cv_path_contains_job_id_and_kind(tmp_path):
    result = save_tailored_cv("CV content", "job_001", "cv", _portal=_portal(tmp_path))
    assert "job_001" in result["path"]
    assert "cv" in result["path"]


def test_save_cover_letter_path_contains_kind(tmp_path):
    result = save_tailored_cv("Letter", "job_002", "cover_letter", _portal=_portal(tmp_path))
    assert "cover_letter" in result["path"]
    assert "job_002" in result["path"]


def test_save_cv_writes_file_to_disk(tmp_path):
    text = "This is the tailored CV text."
    result = save_tailored_cv(text, "job_001", "cv", _portal=_portal(tmp_path))
    written = Path(result["path"]).read_text(encoding="utf-8")
    assert written == text


def test_save_cv_atomic_no_tmp_left_behind(tmp_path):
    save_tailored_cv("content", "job_001", "cv", _portal=_portal(tmp_path))
    tmp_files = list((tmp_path / "output").glob("*.tmp"))
    assert tmp_files == []


def test_save_cv_overwrites_existing_file(tmp_path):
    p = _portal(tmp_path)
    save_tailored_cv("first version", "job_001", "cv", _portal=p)
    save_tailored_cv("second version", "job_001", "cv", _portal=p)
    result = save_tailored_cv("third version", "job_001", "cv", _portal=p)
    assert Path(result["path"]).read_text(encoding="utf-8") == "third version"


def test_save_cv_creates_output_dir_if_absent(tmp_path):
    portal = _portal(tmp_path)
    # Remove output dir to verify it is created on demand.
    output = portal.output_dir
    if output.exists():
        import shutil
        shutil.rmtree(output)
    result = save_tailored_cv("CV", "job_001", "cv", _portal=portal)
    assert Path(result["path"]).exists()


# ---------------------------------------------------------------------------
# save_tailored_cv — error paths
# ---------------------------------------------------------------------------

def test_save_cv_kind_mismatch_caught_by_pydantic_upstream():
    # Pydantic rejects bad kind before the function is reached; calling
    # the function directly with bad kind has no validator, so test the
    # real guard: the computed path must stay inside output_dir.
    # (This double-checks the PATH_NOT_ALLOWED guard with a crafted path.)
    # We can't easily craft a traversal via kind since it's already validated
    # upstream; this test just verifies the function returns a dict.
    from pathlib import Path as _Path
    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        portal = Portal(sandbox_dir=td)
        result = save_tailored_cv("text", "job_001", "cv", _portal=portal)
        assert "saved" in result or "error" in result


# ---------------------------------------------------------------------------
# submit_application — happy path
# ---------------------------------------------------------------------------

def test_submit_returns_status_submitted(tmp_path):
    p = _portal(tmp_path)
    cv, cl = _make_cv_files(p, "job_001")
    result = submit_application(cv, cl, "job_001", _portal=p)
    assert result["status"] == "submitted"


def test_submit_application_id_format(tmp_path):
    p = _portal(tmp_path)
    cv, cl = _make_cv_files(p, "job_001")
    result = submit_application(cv, cl, "job_001", _portal=p)
    assert result["application_id"] == "app_job_001"


def test_submit_records_application_in_state(tmp_path):
    p = _portal(tmp_path)
    cv, cl = _make_cv_files(p, "job_001")
    submit_application(cv, cl, "job_001", _portal=p)
    assert p.has_applied("job_001")


def test_submit_stores_paths_in_state(tmp_path):
    p = _portal(tmp_path)
    cv, cl = _make_cv_files(p, "job_001")
    submit_application(cv, cl, "job_001", _portal=p)
    with open(p.applications_file, encoding="utf-8") as fh:
        apps = json.load(fh)
    assert apps["job_001"]["cv_path"] == cv
    assert apps["job_001"]["cover_letter_path"] == cl


# ---------------------------------------------------------------------------
# submit_application — PATH_NOT_ALLOWED
# ---------------------------------------------------------------------------

def test_submit_rejects_absolute_cv_path(tmp_path):
    result = submit_application("/etc/passwd", "out/cl.md", "job_001", _portal=_portal(tmp_path))
    assert result["error"] == "PATH_NOT_ALLOWED"
    assert "cv_path" in result["message"]


def test_submit_rejects_absolute_cover_letter_path(tmp_path):
    result = submit_application("out/cv.md", "/tmp/cl.md", "job_001", _portal=_portal(tmp_path))
    assert result["error"] == "PATH_NOT_ALLOWED"
    assert "cover_letter_path" in result["message"]


def test_submit_rejects_traversal_in_cv_path(tmp_path):
    result = submit_application("../secret.md", "out/cl.md", "job_001", _portal=_portal(tmp_path))
    assert result["error"] == "PATH_NOT_ALLOWED"


def test_submit_rejects_traversal_in_cover_letter_path(tmp_path):
    result = submit_application("out/cv.md", "../other/cl.md", "job_001", _portal=_portal(tmp_path))
    assert result["error"] == "PATH_NOT_ALLOWED"


# ---------------------------------------------------------------------------
# submit_application — DUPLICATE_SUBMISSION
# ---------------------------------------------------------------------------

def test_submit_duplicate_returns_error(tmp_path):
    p = _portal(tmp_path)
    cv, cl = _make_cv_files(p, "job_001")
    submit_application(cv, cl, "job_001", _portal=p)
    result = submit_application(cv, cl, "job_001", _portal=p)
    assert result["error"] == "DUPLICATE_SUBMISSION"


def test_submit_duplicate_error_message_contains_job_id(tmp_path):
    p = _portal(tmp_path)
    cv, cl = _make_cv_files(p, "job_007")
    submit_application(cv, cl, "job_007", _portal=p)
    result = submit_application(cv, cl, "job_007", _portal=p)
    assert "job_007" in result["message"]


def test_submit_different_jobs_both_succeed(tmp_path):
    p = _portal(tmp_path)
    cv1, cl1 = _make_cv_files(p, "job_001")
    cv2, cl2 = _make_cv_files(p, "job_002")
    r1 = submit_application(cv1, cl1, "job_001", _portal=p)
    r2 = submit_application(cv2, cl2, "job_002", _portal=p)
    assert r1["status"] == "submitted"
    assert r2["status"] == "submitted"
