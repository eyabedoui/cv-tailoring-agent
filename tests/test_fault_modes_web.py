"""
Tests for fault-mode injection in all three web tools: find_jobs, read_job_posting,
submit_application.

Each test uses offline clients so no network or API keys are required.
Tests cover all fault modes (down, timeout, bad_response, fail_once,
reject_duplicate, blocked, unknown) for each tool.

Fault modes and their contexts:
  - down / timeout / bad_response / fail_once / unknown → fire for ALL contexts
  - reject_duplicate → submit only
  - blocked → find_jobs (search) AND read_job_posting (read), not submit
"""

from pathlib import Path

import pytest

from agent.sites import own_job_url
from agent.tools.clients import FakePostingClient
from agent.tools.reads import read_job_posting
from agent.tools.search import find_jobs
from agent.tools.writes import submit_application
from sandbox.faults import check_fault
from sandbox.portal import Portal
from sandbox.seed import seed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seeded_client(tmp_path: Path) -> FakePostingClient:
    seed(postings_dir=tmp_path / "postings")
    return FakePostingClient(sandbox_dir=str(tmp_path))


def _portal(tmp_path: Path) -> Portal:
    return Portal(sandbox_dir=str(tmp_path))


def _make_files(portal: Portal, job_id: str) -> tuple[str, str]:
    cv = f"cv_{job_id}.md"
    cl = f"cover_letter_{job_id}.md"
    (portal.output_dir / cv).write_text("CV", encoding="utf-8")
    (portal.output_dir / cl).write_text("CL", encoding="utf-8")
    return cv, cl


# ---------------------------------------------------------------------------
# FAULT_MODE=down — fires for all three tools
# ---------------------------------------------------------------------------

def test_down_find_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "down")
    result = find_jobs("python", "keejob")
    assert result["error"] == "PORTAL_DOWN"
    assert result["retryable"] is True


def test_down_read_job_posting(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "down")
    client = _seeded_client(tmp_path)
    result = read_job_posting(own_job_url("job_001"), _client=client)
    assert result["error"] == "PORTAL_DOWN"


def test_down_submit_application(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "down")
    portal = _portal(tmp_path)
    result = submit_application("cv.md", "cl.md", "job_001", _portal=portal)
    assert result["error"] == "PORTAL_DOWN"


# ---------------------------------------------------------------------------
# FAULT_MODE=timeout
# ---------------------------------------------------------------------------

def test_timeout_find_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "timeout")
    result = find_jobs("python", "keejob")
    assert result["error"] == "TIMEOUT"
    assert result["retryable"] is True


def test_timeout_read_job_posting(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "timeout")
    client = _seeded_client(tmp_path)
    result = read_job_posting(own_job_url("job_001"), _client=client)
    assert result["error"] == "TIMEOUT"


def test_timeout_submit_application(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "timeout")
    portal = _portal(tmp_path)
    result = submit_application("cv.md", "cl.md", "job_001", _portal=portal)
    assert result["error"] == "TIMEOUT"


# ---------------------------------------------------------------------------
# FAULT_MODE=bad_response
# ---------------------------------------------------------------------------

def test_bad_response_find_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "bad_response")
    result = find_jobs("python", "keejob")
    assert result["error"] == "BAD_RESPONSE"


def test_bad_response_read_job_posting(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "bad_response")
    client = _seeded_client(tmp_path)
    result = read_job_posting(own_job_url("job_001"), _client=client)
    assert result["error"] == "BAD_RESPONSE"


def test_bad_response_submit_application(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "bad_response")
    portal = _portal(tmp_path)
    result = submit_application("cv.md", "cl.md", "job_001", _portal=portal)
    assert result["error"] == "BAD_RESPONSE"


# ---------------------------------------------------------------------------
# FAULT_MODE=fail_once
# ---------------------------------------------------------------------------

def test_fail_once_find_jobs_first_call_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "fail_once")
    result = find_jobs("python", "keejob")
    assert result["error"] == "PORTAL_DOWN"
    assert result["retryable"] is True


def test_fail_once_find_jobs_second_call_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "fail_once")
    find_jobs("python", "keejob")          # first: fails
    result = find_jobs("python", "keejob") # second: succeeds
    assert "error" not in result
    assert result["count"] > 0


def test_fail_once_read_job_posting_first_call_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "fail_once")
    client = _seeded_client(tmp_path)
    result = read_job_posting(own_job_url("job_001"), _client=client)
    assert result["error"] == "PORTAL_DOWN"


def test_fail_once_read_job_posting_second_call_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "fail_once")
    client = _seeded_client(tmp_path)
    read_job_posting(own_job_url("job_001"), _client=client)   # 1: fails
    result = read_job_posting(own_job_url("job_001"), _client=client)  # 2: succeeds
    assert "error" not in result
    assert result["job_id"] == "job_001"


# ---------------------------------------------------------------------------
# FAULT_MODE=reject_duplicate — submit only
# ---------------------------------------------------------------------------

def test_reject_duplicate_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "reject_duplicate")
    portal = _portal(tmp_path)
    result = submit_application("cv.md", "cl.md", "job_001", _portal=portal)
    assert result["error"] == "DUPLICATE_SUBMISSION"


def test_reject_duplicate_does_not_affect_find_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "reject_duplicate")
    result = find_jobs("python", "keejob")
    assert "error" not in result


def test_reject_duplicate_does_not_affect_read(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "reject_duplicate")
    client = _seeded_client(tmp_path)
    result = read_job_posting(own_job_url("job_001"), _client=client)
    assert "error" not in result


# ---------------------------------------------------------------------------
# FAULT_MODE=blocked — search AND read, NOT submit
# ---------------------------------------------------------------------------

def test_blocked_find_jobs_returns_site_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "blocked")
    result = find_jobs("python", "keejob")
    assert result["error"] == "SITE_BLOCKED"
    assert result["retryable"] is False


def test_blocked_read_job_posting_returns_site_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "blocked")
    client = _seeded_client(tmp_path)
    result = read_job_posting(own_job_url("job_001"), _client=client)
    assert result["error"] == "SITE_BLOCKED"
    assert result["retryable"] is False


def test_blocked_does_not_affect_submit(tmp_path, monkeypatch):
    """blocked mode must not fire on submit — submit goes through."""
    monkeypatch.setenv("FAULT_MODE", "blocked")
    portal = _portal(tmp_path)
    cv, cl = _make_files(portal, "job_001")
    result = submit_application(cv, cl, "job_001", _portal=portal)
    assert result.get("status") == "submitted"


# ---------------------------------------------------------------------------
# FAULT_MODE=unknown
# ---------------------------------------------------------------------------

def test_unknown_fault_find_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "unknown")
    result = find_jobs("python", "keejob")
    assert result.get("error") == "FAULT_INJECTED"


def test_unknown_fault_read_job_posting(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "unknown")
    client = _seeded_client(tmp_path)
    result = read_job_posting(own_job_url("job_001"), _client=client)
    assert result.get("error") == "FAULT_INJECTED"


def test_unknown_fault_submit_application(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "unknown")
    portal = _portal(tmp_path)
    result = submit_application("cv.md", "cl.md", "job_001", _portal=portal)
    assert result.get("error") == "FAULT_INJECTED"


# ---------------------------------------------------------------------------
# check_fault context matrix unit tests
# ---------------------------------------------------------------------------

def test_check_fault_blocked_fires_for_search(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "blocked")
    result = check_fault("search", tmp_path)
    assert result is not None
    assert result["error"] == "SITE_BLOCKED"


def test_check_fault_blocked_fires_for_read(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "blocked")
    result = check_fault("read", tmp_path)
    assert result is not None
    assert result["error"] == "SITE_BLOCKED"


def test_check_fault_blocked_does_not_fire_for_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "blocked")
    result = check_fault("submit", tmp_path)
    assert result is None


def test_check_fault_reject_duplicate_fires_only_for_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "reject_duplicate")
    assert check_fault("submit", tmp_path) is not None
    assert check_fault("read", tmp_path) is None
    assert check_fault("search", tmp_path) is None


# ---------------------------------------------------------------------------
# Smoke test: pytest never constructs real clients
# ---------------------------------------------------------------------------

def test_web_mode_is_fake_in_pytest_environment():
    """The offline guard autouse fixture must keep WEB_MODE=fake in all tests."""
    import os
    assert os.environ.get("WEB_MODE", "fake") == "fake"
