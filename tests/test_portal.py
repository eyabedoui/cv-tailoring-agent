
"""
Tests for sandbox/portal.py.

All tests use a tmp_path fixture for full isolation — no shared sandbox state.
"""

import json
from pathlib import Path

import pytest

from sandbox.portal import Portal
from sandbox.seed import POSTINGS, seed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_portal(tmp_path: Path) -> Portal:
    """Return a Portal rooted at tmp_path."""
    return Portal(sandbox_dir=str(tmp_path))


def _seed_into(tmp_path: Path) -> None:
    """Seed posting files into tmp_path/postings/."""
    seed(postings_dir=tmp_path / "postings")


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def test_portal_creates_state_dir(tmp_path):
    _make_portal(tmp_path)
    assert (tmp_path / "state").is_dir()


def test_portal_creates_output_dir(tmp_path):
    _make_portal(tmp_path)
    assert (tmp_path / "output").is_dir()


# ---------------------------------------------------------------------------
# get_posting
# ---------------------------------------------------------------------------

def test_get_posting_returns_none_for_missing_job(tmp_path):
    portal = _make_portal(tmp_path)
    assert portal.get_posting("job_999") is None


def test_get_posting_returns_dict_after_seed(tmp_path):
    _seed_into(tmp_path)
    portal = _make_portal(tmp_path)
    posting = portal.get_posting("job_001")
    assert posting is not None
    assert posting["job_id"] == "job_001"
    assert posting["title"] == "Junior AI Engineer"
    assert isinstance(posting["requirements"], list)
    assert len(posting["requirements"]) == 4


def test_get_posting_has_text_field(tmp_path):
    _seed_into(tmp_path)
    portal = _make_portal(tmp_path)
    posting = portal.get_posting("job_001")
    assert "text" in posting
    assert len(posting["text"]) > 20


def test_get_posting_all_25_accessible_after_seed(tmp_path):
    _seed_into(tmp_path)
    portal = _make_portal(tmp_path)
    for i in range(1, 26):
        job_id = f"job_{i:03d}"
        assert portal.get_posting(job_id) is not None, f"{job_id} not found"


# ---------------------------------------------------------------------------
# has_applied
# ---------------------------------------------------------------------------

def test_has_applied_returns_false_initially(tmp_path):
    portal = _make_portal(tmp_path)
    assert portal.has_applied("job_001") is False


def test_has_applied_returns_false_when_file_absent(tmp_path):
    portal = _make_portal(tmp_path)
    assert not (tmp_path / "state" / "applications.json").exists()
    assert portal.has_applied("job_001") is False


# ---------------------------------------------------------------------------
# record_application + has_applied round-trip
# ---------------------------------------------------------------------------

def test_record_application_creates_file(tmp_path):
    portal = _make_portal(tmp_path)
    portal.record_application("job_001", "out/cv.md", "out/cl.md")
    assert portal.applications_file.exists()


def test_has_applied_true_after_record(tmp_path):
    portal = _make_portal(tmp_path)
    portal.record_application("job_001", "out/cv.md", "out/cl.md")
    assert portal.has_applied("job_001") is True


def test_has_applied_false_for_different_job(tmp_path):
    portal = _make_portal(tmp_path)
    portal.record_application("job_001", "out/cv.md", "out/cl.md")
    assert portal.has_applied("job_002") is False


def test_record_application_stores_paths(tmp_path):
    portal = _make_portal(tmp_path)
    portal.record_application("job_001", "out/cv_job_001.md", "out/cl_job_001.md")
    with open(portal.applications_file, encoding="utf-8") as fh:
        apps = json.load(fh)
    assert apps["job_001"]["cv_path"] == "out/cv_job_001.md"
    assert apps["job_001"]["cover_letter_path"] == "out/cl_job_001.md"


def test_record_application_stores_applied_at_timestamp(tmp_path):
    portal = _make_portal(tmp_path)
    portal.record_application("job_001", "cv.md", "cl.md")
    with open(portal.applications_file, encoding="utf-8") as fh:
        apps = json.load(fh)
    assert "applied_at" in apps["job_001"]


def test_record_multiple_applications(tmp_path):
    portal = _make_portal(tmp_path)
    portal.record_application("job_001", "cv1.md", "cl1.md")
    portal.record_application("job_002", "cv2.md", "cl2.md")
    assert portal.has_applied("job_001")
    assert portal.has_applied("job_002")
    with open(portal.applications_file, encoding="utf-8") as fh:
        apps = json.load(fh)
    assert len(apps) == 2


def test_record_application_overwrites_existing_entry(tmp_path):
    portal = _make_portal(tmp_path)
    portal.record_application("job_001", "old_cv.md", "old_cl.md")
    portal.record_application("job_001", "new_cv.md", "new_cl.md")
    with open(portal.applications_file, encoding="utf-8") as fh:
        apps = json.load(fh)
    assert apps["job_001"]["cv_path"] == "new_cv.md"


def test_record_application_uses_atomic_write(tmp_path):
    """After record, no .tmp file should remain."""
    portal = _make_portal(tmp_path)
    portal.record_application("job_001", "cv.md", "cl.md")
    assert not (tmp_path / "state" / "applications.tmp").exists()


# ---------------------------------------------------------------------------
# seed data consistency
# ---------------------------------------------------------------------------

def test_seed_produces_25_postings(tmp_path):
    _seed_into(tmp_path)
    files = list((tmp_path / "postings").glob("job_*.json"))
    assert len(files) == 25


def test_seed_postings_have_required_fields(tmp_path):
    _seed_into(tmp_path)
    portal = _make_portal(tmp_path)
    required = {"job_id", "title", "company", "requirements", "text"}
    for posting in POSTINGS:
        loaded = portal.get_posting(posting["job_id"])
        assert required.issubset(loaded.keys()), f"{posting['job_id']} missing fields"


def test_seed_all_job_ids_match_filename(tmp_path):
    _seed_into(tmp_path)
    postings_dir = tmp_path / "postings"
    for path in postings_dir.glob("job_*.json"):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["job_id"] == path.stem


def test_seed_requirements_are_non_empty_lists(tmp_path):
    _seed_into(tmp_path)
    portal = _make_portal(tmp_path)
    for posting in POSTINGS:
        loaded = portal.get_posting(posting["job_id"])
        assert isinstance(loaded["requirements"], list)
        assert len(loaded["requirements"]) > 0
