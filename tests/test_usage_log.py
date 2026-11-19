"""
Tests for agent/tools/usage_log.py — all offline.
"""
import json
import pytest

from agent.tools.usage_log import log_usage


# ---------------------------------------------------------------------------
# Basic write
# ---------------------------------------------------------------------------

def test_log_creates_file(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    log_usage("find_jobs", "www.keejob.com", "success", _log_path=log_path)
    assert log_path.exists()


def test_log_entry_is_valid_json(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    log_usage("find_jobs", "www.keejob.com", "success", _log_path=log_path)
    line = log_path.read_text(encoding="utf-8").strip()
    entry = json.loads(line)
    assert isinstance(entry, dict)


def test_log_entry_has_required_fields(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    log_usage("read_job_posting", "www.keejob.com", "success", _log_path=log_path)
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    for field in ("timestamp", "tool", "host", "status"):
        assert field in entry, f"Missing field: {field}"


def test_log_entry_values(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    log_usage("submit_application", "127.0.0.1", "submitted", _log_path=log_path)
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["tool"] == "submit_application"
    assert entry["host"] == "127.0.0.1"
    assert entry["status"] == "submitted"


def test_log_detail_field_included_when_set(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    log_usage("find_jobs", "host.com", "error", detail="PORTAL_DOWN", _log_path=log_path)
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["detail"] == "PORTAL_DOWN"


def test_log_detail_absent_when_empty(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    log_usage("find_jobs", "host.com", "success", _log_path=log_path)
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert "detail" not in entry


# ---------------------------------------------------------------------------
# Multiple entries
# ---------------------------------------------------------------------------

def test_multiple_entries_appended(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    log_usage("find_jobs", "host.com", "success", _log_path=log_path)
    log_usage("find_jobs", "host.com", "success", _log_path=log_path)
    log_usage("read_job_posting", "host.com", "success", _log_path=log_path)
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3


def test_multiple_entries_all_valid_json(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    for _ in range(5):
        log_usage("find_jobs", "host.com", "success", _log_path=log_path)
    for line in log_path.read_text(encoding="utf-8").splitlines():
        json.loads(line)  # must not raise


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------

def test_oserror_does_not_raise(tmp_path):
    """Writing to an unwritable path must not raise or crash the agent."""
    bad_path = tmp_path / "nonexistent_dir" / "sub" / "log.jsonl"
    # Remove mkdir so parent dir doesn't exist and open will fail on Windows
    # (can't mkdir_parents because that's what log_usage does internally — we just
    # trust the except OSError clause handles unexpected errors)
    # We test by patching open to raise OSError.
    import builtins
    original_open = builtins.open

    def _bad_open(path, *args, **kwargs):
        if str(path).endswith("log.jsonl"):
            raise OSError("simulated write error")
        return original_open(path, *args, **kwargs)

    import unittest.mock as mock
    with mock.patch("builtins.open", _bad_open):
        log_usage("find_jobs", "host.com", "success", _log_path=tmp_path / "log.jsonl")
    # No exception raised — test passes by reaching here


# ---------------------------------------------------------------------------
# Timestamp format
# ---------------------------------------------------------------------------

def test_timestamp_is_iso8601(tmp_path):
    from datetime import datetime
    log_path = tmp_path / "log.jsonl"
    log_usage("find_jobs", "host.com", "success", _log_path=log_path)
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    ts = entry["timestamp"]
    parsed = datetime.fromisoformat(ts)
    assert parsed is not None
