"""
Tests for BrowserSubmitClient and the W5 submit_application integration.

All tests are offline — browser_use.Agent and browser_use.llm.ChatOpenAI are
monkeypatched so no real browser is launched and no API keys are needed.
"""
import pytest

import browser_use
import browser_use.llm

from agent.tools.clients import BrowserSubmitClient
from agent.tools.writes import submit_application
from sandbox.portal import Portal


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _FakeSubmitOutput:
    def __init__(self, status="submitted", application_id="app_job_001"):
        self.status = status
        self.application_id = application_id


class _FakeHistory:
    def __init__(self, output):
        self._output = output

    @property
    def structured_output(self):
        return self._output


@pytest.fixture()
def mock_browser_submit(monkeypatch):
    """Patch browser_use.Agent to simulate a successful submission."""

    class _FakeAgent:
        def __init__(self, task, llm, output_model_schema=None, **kwargs):
            pass

        async def run(self, max_steps=10, timeout=60, **kwargs):
            return _FakeHistory(_FakeSubmitOutput("submitted", "app_job_001"))

    class _FakeLLM:
        def __init__(self, model="", api_key="", **kwargs):
            pass

    monkeypatch.setattr(browser_use, "Agent", _FakeAgent)
    monkeypatch.setattr(browser_use.llm, "ChatOpenAI", _FakeLLM)


# ---------------------------------------------------------------------------
# BrowserSubmitClient.submit
# ---------------------------------------------------------------------------

def test_browser_submit_returns_submitted(mock_browser_submit):
    client = BrowserSubmitClient()
    result = client.submit("job_001", "http://127.0.0.1:5000/apply/job_001")
    assert result["status"] == "submitted"


def test_browser_submit_returns_application_id(mock_browser_submit):
    client = BrowserSubmitClient()
    result = client.submit("job_001", "http://127.0.0.1:5000/apply/job_001")
    assert result["application_id"] == "app_job_001"


def test_browser_submit_no_error_on_success(mock_browser_submit):
    client = BrowserSubmitClient()
    result = client.submit("job_001", "http://127.0.0.1:5000/apply/job_001")
    assert "error" not in result


def test_browser_submit_none_output_returns_portal_down(monkeypatch):
    """When structured_output is None, return PORTAL_DOWN."""

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

    client = BrowserSubmitClient()
    result = client.submit("job_001", "http://127.0.0.1:5000/apply/job_001")
    assert result["error"] == "PORTAL_DOWN"


def test_browser_submit_non_submitted_status_returns_portal_down(monkeypatch):
    """When status is not 'submitted', return PORTAL_DOWN."""

    class _FakeAgentFail:
        def __init__(self, task, llm, **kwargs):
            pass

        async def run(self, **kwargs):
            return _FakeHistory(_FakeSubmitOutput(status="error", application_id=""))

    class _FakeLLM:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(browser_use, "Agent", _FakeAgentFail)
    monkeypatch.setattr(browser_use.llm, "ChatOpenAI", _FakeLLM)

    client = BrowserSubmitClient()
    result = client.submit("job_001", "http://127.0.0.1:5000/apply/job_001")
    assert result["error"] == "PORTAL_DOWN"


def test_browser_submit_uses_job_id_in_fallback_application_id(monkeypatch):
    """When application_id is empty, falls back to 'app_{job_id}'."""

    class _FakeAgentEmpty:
        def __init__(self, task, llm, **kwargs):
            pass

        async def run(self, **kwargs):
            return _FakeHistory(_FakeSubmitOutput(status="submitted", application_id=""))

    class _FakeLLM:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(browser_use, "Agent", _FakeAgentEmpty)
    monkeypatch.setattr(browser_use.llm, "ChatOpenAI", _FakeLLM)

    client = BrowserSubmitClient()
    result = client.submit("job_042", "http://127.0.0.1:5000/apply/job_042")
    assert result["application_id"] == "app_job_042"


# ---------------------------------------------------------------------------
# submit_application with _submit_client injection
# ---------------------------------------------------------------------------

class _FakeSubmitClient:
    def __init__(self, response):
        self._response = response

    def submit(self, job_id, apply_url):
        return self._response


def test_submit_application_uses_submit_client_when_injected(tmp_path):
    portal = Portal(sandbox_dir=str(tmp_path))
    (portal.output_dir / "cv_job_001.md").write_text("CV", encoding="utf-8")
    (portal.output_dir / "cover_letter_job_001.md").write_text("CL", encoding="utf-8")
    # Simulate Flask server having recorded the application after browser submit
    portal.record_application("job_001", "cv_job_001.md", "cover_letter_job_001.md")
    client = _FakeSubmitClient({"status": "submitted", "application_id": "app_job_001"})
    result = submit_application(
        "cv_job_001.md", "cover_letter_job_001.md", "job_001",
        _portal=portal,
        _submit_client=client,
    )
    assert result["status"] == "submitted"


def test_submit_application_fault_fires_before_submit_client(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULT_MODE", "down")
    called = []

    class _TrackingClient:
        def submit(self, job_id, apply_url):
            called.append(job_id)
            return {"status": "submitted", "application_id": "app_job_001"}

    result = submit_application(
        "output/cv.md", "output/cl.md", "job_001",
        _portal=Portal(sandbox_dir=str(tmp_path)),
        _submit_client=_TrackingClient(),
    )
    assert result["error"] == "PORTAL_DOWN"
    assert called == [], "submit client must not be called when fault fires"


def test_submit_application_live_mode_uses_browser_client(tmp_path, monkeypatch, mock_browser_submit):
    monkeypatch.setenv("WEB_MODE", "live")
    portal = Portal(sandbox_dir=str(tmp_path))
    (portal.output_dir / "cv_job_001.md").write_text("CV", encoding="utf-8")
    (portal.output_dir / "cover_letter_job_001.md").write_text("CL", encoding="utf-8")
    # Simulate Flask server having recorded the application after browser submit
    portal.record_application("job_001", "cv_job_001.md", "cover_letter_job_001.md")
    result = submit_application(
        "cv_job_001.md", "cover_letter_job_001.md", "job_001",
        _portal=portal,
    )
    assert result["status"] == "submitted"


def test_submit_application_fake_mode_still_uses_portal(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_MODE", "fake")
    portal = Portal(sandbox_dir=str(tmp_path))
    (portal.output_dir / "cv_job_001.md").write_text("CV", encoding="utf-8")
    (portal.output_dir / "cover_letter_job_001.md").write_text("CL", encoding="utf-8")
    result = submit_application("cv_job_001.md", "cover_letter_job_001.md", "job_001", _portal=portal)
    assert result["status"] == "submitted"
    assert portal.has_applied("job_001")
