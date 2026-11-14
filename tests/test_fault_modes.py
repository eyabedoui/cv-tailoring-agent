
"""
Tests for sandbox/faults.py and FAULT_MODE integration in read_job_posting
and submit_application.

Each test uses a tmp_path-backed Portal for state isolation and
monkeypatch.setenv to control FAULT_MODE without affecting other tests.
"""

import json
from pathlib import Path

import pytest

from agent.tools.reads import read_job_posting
from agent.tools.writes import submit_application
from sandbox.faults import check_fault
from sandbox.portal import Portal
from sandbox.seed import seed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seeded_portal(tmp_path: Path) -> Portal:
    seed(postings_dir=tmp_path / "postings")
    return Portal(sandbox_dir=str(tmp_path))


def _portal(tmp_path: Path) -> Portal:
    return Portal(sandbox_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# FAULT_MODE=down
# ---------------------------------------------------------------------------

def test_down_returns_portal_down_on_read(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "down")
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert result["error"] == "PORTAL_DOWN"


def test_down_is_retryable_on_read(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "down")
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert result["retryable"] is True


def test_down_returns_portal_down_on_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "down")
    portal = _portal(tmp_path)
    result = submit_application("out/cv.md", "out/cl.md", "job_001", _portal=portal)
    assert result["error"] == "PORTAL_DOWN"


# ---------------------------------------------------------------------------
# FAULT_MODE=timeout
# ---------------------------------------------------------------------------

def test_timeout_returns_timeout_on_read(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "timeout")
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert result["error"] == "TIMEOUT"
    assert result["retryable"] is True


def test_timeout_returns_timeout_on_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "timeout")
    portal = _portal(tmp_path)
    result = submit_application("out/cv.md", "out/cl.md", "job_001", _portal=portal)
    assert result["error"] == "TIMEOUT"


# ---------------------------------------------------------------------------
# FAULT_MODE=bad_response
# ---------------------------------------------------------------------------

def test_bad_response_on_read(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "bad_response")
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert result["error"] == "BAD_RESPONSE"


def test_bad_response_not_retryable(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "bad_response")
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert result.get("retryable") is False


def test_bad_response_on_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "bad_response")
    portal = _portal(tmp_path)
    result = submit_application("out/cv.md", "out/cl.md", "job_001", _portal=portal)
    assert result["error"] == "BAD_RESPONSE"


# ---------------------------------------------------------------------------
# FAULT_MODE=fail_once
# ---------------------------------------------------------------------------

def test_fail_once_first_call_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "fail_once")
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert result["error"] == "PORTAL_DOWN"
    assert result["retryable"] is True


def test_fail_once_second_call_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "fail_once")
    portal = _seeded_portal(tmp_path)
    read_job_posting("mock://jobs/job_001", _portal=portal)  # first: fails
    result = read_job_posting("mock://jobs/job_001", _portal=portal)  # second: succeeds
    assert result.get("job_id") == "job_001"
    assert "error" not in result


def test_fail_once_writes_fault_state_file(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "fail_once")
    portal = _seeded_portal(tmp_path)
    read_job_posting("mock://jobs/job_001", _portal=portal)
    state_file = portal.state_dir / "fault_state.json"
    assert state_file.exists()
    with open(state_file, encoding="utf-8") as fh:
        state = json.load(fh)
    assert state["fail_once_fired"] is True


def test_fail_once_third_call_also_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "fail_once")
    portal = _seeded_portal(tmp_path)
    read_job_posting("mock://jobs/job_001", _portal=portal)  # 1: fails
    read_job_posting("mock://jobs/job_001", _portal=portal)  # 2: succeeds
    result = read_job_posting("mock://jobs/job_001", _portal=portal)  # 3: succeeds
    assert result.get("job_id") == "job_001"


# ---------------------------------------------------------------------------
# FAULT_MODE=reject_duplicate
# ---------------------------------------------------------------------------

def test_reject_duplicate_on_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "reject_duplicate")
    portal = _portal(tmp_path)
    result = submit_application("out/cv.md", "out/cl.md", "job_001", _portal=portal)
    assert result["error"] == "DUPLICATE_SUBMISSION"


def test_reject_duplicate_does_not_affect_read(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "reject_duplicate")
    portal = _seeded_portal(tmp_path)
    # read_job_posting should NOT be affected by reject_duplicate.
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert "error" not in result
    assert result.get("job_id") == "job_001"


def test_reject_duplicate_does_not_record_application(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "reject_duplicate")
    portal = _portal(tmp_path)
    submit_application("out/cv.md", "out/cl.md", "job_001", _portal=portal)
    # The fault fires before record_application, so the application is not stored.
    assert not portal.has_applied("job_001")


# ---------------------------------------------------------------------------
# FAULT_MODE=unknown
# ---------------------------------------------------------------------------

def test_unknown_fault_returns_non_standard_error_code(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "unknown")
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    # "FAULT_INJECTED" is not in ERROR_CODES so is_error() returns False.
    assert result.get("error") == "FAULT_INJECTED"


def test_unknown_fault_on_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "unknown")
    portal = _portal(tmp_path)
    result = submit_application("out/cv.md", "out/cl.md", "job_001", _portal=portal)
    assert result.get("error") == "FAULT_INJECTED"


# ---------------------------------------------------------------------------
# No FAULT_MODE (default) — sanity checks that normal path is unaffected
# ---------------------------------------------------------------------------

def test_no_fault_mode_read_succeeds(tmp_path, monkeypatch):
    monkeypatch.delenv("FAULT_MODE", raising=False)
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert result.get("job_id") == "job_001"


def test_no_fault_mode_submit_succeeds(tmp_path, monkeypatch):
    monkeypatch.delenv("FAULT_MODE", raising=False)
    portal = _portal(tmp_path)
    result = submit_application("out/cv.md", "out/cl.md", "job_001", _portal=portal)
    assert result["status"] == "submitted"


# ---------------------------------------------------------------------------
# check_fault direct unit tests
# ---------------------------------------------------------------------------

def test_check_fault_empty_string_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "")
    assert check_fault("read", tmp_path) is None


def test_check_fault_reject_duplicate_only_fires_for_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "reject_duplicate")
    result = check_fault("read", tmp_path)
    assert result is None  # reject_duplicate does not affect reads
