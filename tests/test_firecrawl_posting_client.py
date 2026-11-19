"""
Tests for FirecrawlPostingClient — all offline.

firecrawl.V1FirecrawlApp is monkeypatched so no real HTTP calls are made
and no API key is needed.
"""
import pytest

import firecrawl

from agent.tools.clients import FirecrawlPostingClient, FakePostingClient
from agent.tools.reads import _get_client


# ---------------------------------------------------------------------------
# Stub for V1ScrapeResponse
# ---------------------------------------------------------------------------

class _FakeScrapeResponse:
    def __init__(self, markdown="", success=True):
        self.markdown = markdown
        self.success = success


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_firecrawl(monkeypatch):
    """Patch firecrawl.V1FirecrawlApp to avoid real network calls."""
    _MARKDOWN = """\
# AI Engineer
**Company:** TechNova

## Requirements
- Python
- TensorFlow

## Description
Build AI solutions at scale.
"""

    class _FakeApp:
        def __init__(self, api_key="", **kwargs):
            pass

        def scrape_url(self, url, formats=None, **kwargs):
            return _FakeScrapeResponse(markdown=_MARKDOWN)

    monkeypatch.setattr(firecrawl, "V1FirecrawlApp", _FakeApp)
    return _MARKDOWN


# ---------------------------------------------------------------------------
# FirecrawlPostingClient.fetch
# ---------------------------------------------------------------------------

def test_firecrawl_fetch_returns_markdown_key(mock_firecrawl):
    client = FirecrawlPostingClient()
    result = client.fetch("https://www.keejob.com/offres-emploi/42")
    assert "markdown" in result


def test_firecrawl_fetch_returns_url_key(mock_firecrawl):
    url = "https://www.keejob.com/offres-emploi/42"
    client = FirecrawlPostingClient()
    result = client.fetch(url)
    assert result["url"] == url


def test_firecrawl_fetch_no_error_on_success(mock_firecrawl):
    client = FirecrawlPostingClient()
    result = client.fetch("https://www.keejob.com/offres-emploi/42")
    assert "error" not in result


def test_firecrawl_fetch_empty_markdown_returns_not_found(monkeypatch):
    class _FakeEmptyApp:
        def __init__(self, **kwargs):
            pass

        def scrape_url(self, url, **kwargs):
            return _FakeScrapeResponse(markdown="")

    monkeypatch.setattr(firecrawl, "V1FirecrawlApp", _FakeEmptyApp)
    client = FirecrawlPostingClient()
    result = client.fetch("https://www.keejob.com/offres-emploi/99")
    assert result["error"] == "NOT_FOUND"


def test_firecrawl_fetch_exception_returns_portal_down(monkeypatch):
    class _FakeErrorApp:
        def __init__(self, **kwargs):
            pass

        def scrape_url(self, url, **kwargs):
            raise ConnectionError("network unreachable")

    monkeypatch.setattr(firecrawl, "V1FirecrawlApp", _FakeErrorApp)
    client = FirecrawlPostingClient()
    result = client.fetch("https://www.keejob.com/offres-emploi/99")
    assert result["error"] == "PORTAL_DOWN"


def test_firecrawl_fetch_respects_fault_mode(monkeypatch, tmp_path):
    """FAULT_MODE=down fires before Firecrawl is called."""
    monkeypatch.setenv("FAULT_MODE", "down")
    monkeypatch.setenv("SANDBOX_DIR", str(tmp_path))

    # Ensure state dir exists
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)

    # Patch V1FirecrawlApp to verify it is NOT called
    called = []

    class _FakeApp:
        def __init__(self, **kwargs):
            pass

        def scrape_url(self, url, **kwargs):
            called.append(url)
            return _FakeScrapeResponse(markdown="Anything")

    monkeypatch.setattr(firecrawl, "V1FirecrawlApp", _FakeApp)

    client = FirecrawlPostingClient()
    result = client.fetch("https://www.keejob.com/offres-emploi/42")
    assert result["error"] == "PORTAL_DOWN"
    assert called == [], "V1FirecrawlApp.scrape_url should not be called when fault fires"


# ---------------------------------------------------------------------------
# _get_client factory
# ---------------------------------------------------------------------------

def test_get_client_live_returns_firecrawl(monkeypatch):
    import agent.tools.reads as _r
    monkeypatch.setattr(_r, "_client_instance", None)
    monkeypatch.setenv("WEB_MODE", "live")
    client = _r._get_client()
    assert isinstance(client, FirecrawlPostingClient)
    monkeypatch.setattr(_r, "_client_instance", None)  # clean up


def test_get_client_fake_returns_fake(monkeypatch):
    import agent.tools.reads as _r
    monkeypatch.setattr(_r, "_client_instance", None)
    monkeypatch.setenv("WEB_MODE", "fake")
    client = _r._get_client()
    assert isinstance(client, FakePostingClient)
    monkeypatch.setattr(_r, "_client_instance", None)
