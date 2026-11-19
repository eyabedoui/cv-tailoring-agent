"""
Tests for agent/sites.py — allowlist loading, URL validation, host matching.

All tests are offline.  Tests that need a custom allowlist use the
CV_AGENT_ALLOWED_SITES env var and a tmp_path JSON file.
"""

import json
from pathlib import Path

import pytest

from agent.sites import (
    _load_allowlist_cached,
    host_for,
    is_url_allowed,
    load_allowlist,
    site_names,
    url_belongs_to_site,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_allowlist(tmp_path: Path, data: dict) -> str:
    """Write a custom allowlist JSON and return the path string."""
    p = tmp_path / "allowlist.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def _custom_env(monkeypatch, tmp_path, data):
    """Set CV_AGENT_ALLOWED_SITES to a tmp file and clear the lru_cache."""
    path = _write_allowlist(tmp_path, data)
    monkeypatch.setenv("CV_AGENT_ALLOWED_SITES", path)
    _load_allowlist_cached.cache_clear()
    return path


# ---------------------------------------------------------------------------
# load_allowlist / site_names / host_for
# ---------------------------------------------------------------------------

def test_default_allowlist_loads():
    _load_allowlist_cached.cache_clear()
    data = load_allowlist()
    assert "sites" in data


def test_site_names_returns_sorted_enabled():
    _load_allowlist_cached.cache_clear()
    names = site_names()
    assert "tanitjobs" in names
    assert "keejob" in names
    assert "weworkremotely" in names
    assert names == sorted(names)


def test_host_for_tanitjobs():
    _load_allowlist_cached.cache_clear()
    assert host_for("tanitjobs") == "www.tanitjobs.com"


def test_host_for_keejob():
    _load_allowlist_cached.cache_clear()
    assert host_for("keejob") == "www.keejob.com"


def test_host_for_weworkremotely():
    _load_allowlist_cached.cache_clear()
    assert host_for("weworkremotely") == "weworkremotely.com"


def test_disabled_site_not_in_site_names(monkeypatch, tmp_path):
    data = {
        "sites": {
            "enabled_site": {"host": "enabled.example.com", "enabled": True},
            "disabled_site": {"host": "disabled.example.com", "enabled": False},
        }
    }
    _custom_env(monkeypatch, tmp_path, data)
    names = site_names()
    assert "enabled_site" in names
    assert "disabled_site" not in names


# ---------------------------------------------------------------------------
# is_url_allowed — valid cases
# ---------------------------------------------------------------------------

def test_is_url_allowed_exact_host():
    _load_allowlist_cached.cache_clear()
    assert is_url_allowed("https://www.tanitjobs.com/jobs/123") is True


def test_is_url_allowed_subdomain():
    _load_allowlist_cached.cache_clear()
    # jobs.weworkremotely.com is a subdomain of weworkremotely.com
    assert is_url_allowed("https://jobs.weworkremotely.com/remote/123") is True


def test_is_url_allowed_uppercase_scheme_normalised():
    _load_allowlist_cached.cache_clear()
    # urlparse handles scheme case; we normalise to lowercase
    assert is_url_allowed("HTTPS://www.tanitjobs.com/job/1") is True


def test_is_url_allowed_uppercase_host_normalised():
    _load_allowlist_cached.cache_clear()
    assert is_url_allowed("https://WWW.TANITJOBS.COM/job/1") is True


def test_is_url_allowed_trailing_dot_host():
    _load_allowlist_cached.cache_clear()
    # Trailing dot on hostname is stripped before comparison
    assert is_url_allowed("https://www.tanitjobs.com./job/1") is True


# ---------------------------------------------------------------------------
# is_url_allowed — invalid cases
# ---------------------------------------------------------------------------

def test_is_url_allowed_rejects_http():
    _load_allowlist_cached.cache_clear()
    assert is_url_allowed("http://www.tanitjobs.com/jobs/123") is False


def test_is_url_allowed_rejects_unknown_host():
    _load_allowlist_cached.cache_clear()
    assert is_url_allowed("https://evil.com/jobs/123") is False


def test_is_url_allowed_rejects_userinfo():
    _load_allowlist_cached.cache_clear()
    # @-based credential injection: https://evil@trusted.com
    assert is_url_allowed("https://evil@www.tanitjobs.com/job/1") is False


def test_is_url_allowed_rejects_userinfo_password():
    _load_allowlist_cached.cache_clear()
    assert is_url_allowed("https://user:pass@www.keejob.com/job/1") is False


def test_is_url_allowed_rejects_lookalike_suffix():
    _load_allowlist_cached.cache_clear()
    # weworkremotely.com.evil.io is NOT a subdomain of weworkremotely.com
    assert is_url_allowed("https://weworkremotely.com.evil.io/job") is False


def test_is_url_allowed_rejects_partial_host_match():
    _load_allowlist_cached.cache_clear()
    # "fakeweworkremotely.com" contains "weworkremotely.com" as a suffix
    # but is not a proper subdomain
    assert is_url_allowed("https://fakeweworkremotely.com/job") is False


def test_is_url_allowed_rejects_empty_string():
    _load_allowlist_cached.cache_clear()
    assert is_url_allowed("") is False


def test_is_url_allowed_rejects_mock_scheme():
    _load_allowlist_cached.cache_clear()
    assert is_url_allowed("mock://jobs/job_001") is False


def test_is_url_allowed_rejects_ftp():
    _load_allowlist_cached.cache_clear()
    assert is_url_allowed("ftp://www.tanitjobs.com/jobs/1") is False


# ---------------------------------------------------------------------------
# url_belongs_to_site
# ---------------------------------------------------------------------------

def test_url_belongs_to_site_exact_match():
    _load_allowlist_cached.cache_clear()
    assert url_belongs_to_site("https://www.keejob.com/jobs/1", "keejob") is True


def test_url_belongs_to_site_subdomain():
    _load_allowlist_cached.cache_clear()
    assert url_belongs_to_site("https://remote.weworkremotely.com/job/1", "weworkremotely") is True


def test_url_belongs_to_site_wrong_site():
    _load_allowlist_cached.cache_clear()
    assert url_belongs_to_site("https://www.tanitjobs.com/job/1", "keejob") is False


def test_url_belongs_to_site_unknown_site():
    _load_allowlist_cached.cache_clear()
    assert url_belongs_to_site("https://www.evil.com/job/1", "unknown_site") is False


def test_url_belongs_to_site_rejects_http():
    _load_allowlist_cached.cache_clear()
    assert url_belongs_to_site("http://www.tanitjobs.com/job/1", "tanitjobs") is False


def test_url_belongs_to_site_rejects_userinfo():
    _load_allowlist_cached.cache_clear()
    assert url_belongs_to_site("https://evil@www.tanitjobs.com/job/1", "tanitjobs") is False
