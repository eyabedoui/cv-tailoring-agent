"""
W8 smoke tests — verify the entire B-WEB stack wires together correctly.

All tests are offline. They check imports, protocol conformance, and
factory wiring across W3–W7 without hitting any real network or browser.
"""
import pytest


# ---------------------------------------------------------------------------
# Import smoke tests — ensure all new modules are importable
# ---------------------------------------------------------------------------

def test_import_browser_search_client():
    from agent.tools.clients import BrowserSearchClient  # noqa: F401


def test_import_firecrawl_posting_client():
    from agent.tools.clients import FirecrawlPostingClient  # noqa: F401


def test_import_browser_submit_client():
    from agent.tools.clients import BrowserSubmitClient  # noqa: F401


def test_import_throttle():
    from agent.tools.throttle import throttle  # noqa: F401


def test_import_usage_log():
    from agent.tools.usage_log import log_usage  # noqa: F401


def test_import_parse_posting():
    from agent.tools.reads import parse_posting  # noqa: F401


def test_import_snapshot_command():
    from sandbox.manage import snapshot  # noqa: F401


def test_import_setup_web_command():
    from sandbox.manage import setup_web  # noqa: F401


# ---------------------------------------------------------------------------
# Protocol conformance — clients have the right methods
# ---------------------------------------------------------------------------

def test_fake_posting_client_has_fetch():
    from agent.tools.clients import FakePostingClient
    assert callable(FakePostingClient().fetch)


def test_firecrawl_posting_client_has_fetch():
    from agent.tools.clients import FirecrawlPostingClient
    assert callable(FirecrawlPostingClient().fetch)


def test_browser_search_client_has_search():
    from agent.tools.clients import BrowserSearchClient
    assert callable(BrowserSearchClient().search)


def test_browser_submit_client_has_submit():
    from agent.tools.clients import BrowserSubmitClient
    assert callable(BrowserSubmitClient().submit)


def test_fake_search_client_has_search():
    from agent.tools.search import FakeSearchClient
    assert callable(FakeSearchClient().search)


# ---------------------------------------------------------------------------
# Factory wiring — _get_client and _get_search_client return expected types
# ---------------------------------------------------------------------------

def test_get_client_default_is_fake(monkeypatch):
    import agent.tools.reads as _r
    monkeypatch.setattr(_r, "_client_instance", None)
    monkeypatch.delenv("WEB_MODE", raising=False)
    from agent.tools.clients import FakePostingClient
    assert isinstance(_r._get_client(), FakePostingClient)
    monkeypatch.setattr(_r, "_client_instance", None)


def test_get_client_live_is_firecrawl(monkeypatch):
    import agent.tools.reads as _r
    monkeypatch.setattr(_r, "_client_instance", None)
    monkeypatch.setenv("WEB_MODE", "live")
    from agent.tools.clients import FirecrawlPostingClient
    assert isinstance(_r._get_client(), FirecrawlPostingClient)
    monkeypatch.setattr(_r, "_client_instance", None)


def test_get_search_client_default_is_fake(monkeypatch):
    monkeypatch.delenv("WEB_MODE", raising=False)
    from agent.tools.search import _get_search_client, FakeSearchClient
    assert isinstance(_get_search_client(), FakeSearchClient)


def test_get_search_client_live_is_browser(monkeypatch):
    monkeypatch.setenv("WEB_MODE", "live")
    from agent.tools.search import _get_search_client
    from agent.tools.clients import BrowserSearchClient
    assert isinstance(_get_search_client(), BrowserSearchClient)


# ---------------------------------------------------------------------------
# Replay mode — FakePostingClient wiring
# ---------------------------------------------------------------------------

def test_fake_posting_client_replay_missing_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_MODE", "replay")
    from agent.tools.clients import FakePostingClient
    client = FakePostingClient(sandbox_dir=str(tmp_path))
    result = client.fetch("https://www.keejob.com/offres-emploi/42")
    assert result["error"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Throttle — first call does not block
# ---------------------------------------------------------------------------

def test_throttle_first_call_no_sleep(monkeypatch):
    import agent.tools.throttle as _t
    _t._reset()
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(_t, "_clock", lambda: 0.0)
    _t.throttle("smoke-test.host", seconds=3.0)
    assert sleep_calls == []
    _t._reset()


# ---------------------------------------------------------------------------
# Usage log — entry written correctly
# ---------------------------------------------------------------------------

def test_log_usage_writes_entry(tmp_path):
    import json
    from agent.tools.usage_log import log_usage
    log_path = tmp_path / "smoke_log.jsonl"
    log_usage("find_jobs", "www.keejob.com", "success", _log_path=log_path)
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["tool"] == "find_jobs"
    assert entry["status"] == "success"
