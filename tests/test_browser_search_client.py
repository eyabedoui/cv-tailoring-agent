"""
Tests for BrowserSearchClient — all offline.

browser_use.Agent and browser_use.llm.ChatOpenAI are monkeypatched so no
real browser is launched and no API keys are needed.
"""
import pytest

import browser_use
import browser_use.llm

from agent.tools.clients import BrowserSearchClient
from agent.tools.search import _get_search_client, FakeSearchClient


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _FakeJob:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeOutput:
    def __init__(self, jobs):
        self.jobs = [_FakeJob(**j) for j in jobs]


class _FakeHistory:
    def __init__(self, jobs):
        self._jobs = jobs

    @property
    def structured_output(self):
        return _FakeOutput(self._jobs) if self._jobs is not None else None


_SAMPLE_JOBS = [
    {
        "job_id": "job_001",
        "title": "AI Engineer",
        "company": "TechCo",
        "location": "Remote",
        "url": "https://www.keejob.com/jobs/job_001",
        "snippet": "Build AI systems.",
    },
    {
        "job_id": "job_002",
        "title": "Data Scientist",
        "company": "DataCorp",
        "location": "Tunis",
        "url": "https://www.keejob.com/jobs/job_002",
        "snippet": "Analyze data.",
    },
]


@pytest.fixture()
def mock_browser_use(monkeypatch):
    """Patch browser_use.Agent and browser_use.llm.ChatOpenAI to avoid real network calls."""

    class _FakeAgent:
        def __init__(self, task, llm, output_model_schema=None, **kwargs):
            pass

        async def run(self, max_steps=20, timeout=120, **kwargs):
            return _FakeHistory(_SAMPLE_JOBS)

    class _FakeChatOpenAI:
        def __init__(self, model="", api_key="", **kwargs):
            pass

    monkeypatch.setattr(browser_use, "Agent", _FakeAgent)
    monkeypatch.setattr(browser_use.llm, "ChatOpenAI", _FakeChatOpenAI)


# ---------------------------------------------------------------------------
# BrowserSearchClient.search
# ---------------------------------------------------------------------------

def test_browser_search_returns_list(mock_browser_use):
    client = BrowserSearchClient()
    results = client.search("AI engineer", "keejob")
    assert isinstance(results, list)


def test_browser_search_returns_expected_count(mock_browser_use):
    client = BrowserSearchClient()
    results = client.search("AI engineer", "keejob")
    assert len(results) == 2


def test_browser_search_result_has_required_keys(mock_browser_use):
    client = BrowserSearchClient()
    results = client.search("AI engineer", "keejob")
    required = {"job_id", "title", "company", "location", "url", "site", "snippet"}
    for r in results:
        assert required <= r.keys(), f"Missing keys: {required - r.keys()}"


def test_browser_search_site_field_matches_argument(mock_browser_use):
    client = BrowserSearchClient()
    results = client.search("AI engineer", "keejob")
    assert all(r["site"] == "keejob" for r in results)


def test_browser_search_first_title(mock_browser_use):
    client = BrowserSearchClient()
    results = client.search("AI engineer", "keejob")
    assert results[0]["title"] == "AI Engineer"


def test_browser_search_second_company(mock_browser_use):
    client = BrowserSearchClient()
    results = client.search("data", "keejob")
    assert results[1]["company"] == "DataCorp"


def test_browser_search_none_output_returns_empty(monkeypatch):
    """When structured_output is None, return an empty list."""

    class _FakeAgentNone:
        def __init__(self, task, llm, **kwargs):
            pass

        async def run(self, **kwargs):
            return _FakeHistory(None)

    class _FakeLLM:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(browser_use, "Agent", _FakeAgentNone)
    monkeypatch.setattr(browser_use.llm, "ChatOpenAI", _FakeLLM)

    client = BrowserSearchClient()
    results = client.search("anything", "keejob")
    assert results == []


def test_browser_search_empty_jobs_list(monkeypatch):
    """Agent returns structured_output with empty jobs list."""

    class _FakeAgentEmpty:
        def __init__(self, task, llm, **kwargs):
            pass

        async def run(self, **kwargs):
            return _FakeHistory([])

    class _FakeLLM:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(browser_use, "Agent", _FakeAgentEmpty)
    monkeypatch.setattr(browser_use.llm, "ChatOpenAI", _FakeLLM)

    client = BrowserSearchClient()
    results = client.search("anything", "keejob")
    assert results == []


# ---------------------------------------------------------------------------
# _get_search_client factory
# ---------------------------------------------------------------------------

def test_get_search_client_fake_mode(monkeypatch):
    monkeypatch.setenv("WEB_MODE", "fake")
    client = _get_search_client()
    assert isinstance(client, FakeSearchClient)


def test_get_search_client_default_is_fake(monkeypatch):
    monkeypatch.delenv("WEB_MODE", raising=False)
    client = _get_search_client()
    assert isinstance(client, FakeSearchClient)


def test_get_search_client_live_returns_browser_client(monkeypatch):
    monkeypatch.setenv("WEB_MODE", "live")
    client = _get_search_client()
    assert isinstance(client, BrowserSearchClient)


def test_get_search_client_replay_mode_is_fake(monkeypatch):
    monkeypatch.setenv("WEB_MODE", "replay")
    client = _get_search_client()
    assert isinstance(client, FakeSearchClient)
