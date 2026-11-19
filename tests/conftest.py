"""
Session-scoped fixtures shared across the test suite.
"""

import pytest

from sandbox.seed import seed


@pytest.fixture(scope="session", autouse=True)
def seeded_sandbox():
    """Ensure sandbox/postings/ is populated before any test runs."""
    seed()


@pytest.fixture(autouse=True)
def _redirect_logs(tmp_path, monkeypatch):
    """Point the default log directory to a per-test temp dir.

    This prevents the test suite from writing files into the real logs/ dir.
    Tests that explicitly pass log_dir= to AgentLogger are unaffected.
    """
    monkeypatch.setenv("CV_AGENT_LOG_DIR", str(tmp_path))


@pytest.fixture(autouse=True)
def _offline_guard(monkeypatch):
    """
    Ensure all tests run offline by default.

    - Forces WEB_MODE=fake so factory functions return FakeSearchClient /
      FakePostingClient.  Tests that need live behaviour override via
      monkeypatch.setenv("WEB_MODE", "live") within their scope.
    - Clears FAULT_MODE so no fault is active unless a test sets it.
    - Resets per-host throttle state between tests so timing from one test
      never bleeds into the next.
    """
    monkeypatch.setenv("WEB_MODE", "fake")
    monkeypatch.delenv("FAULT_MODE", raising=False)
    yield
    from agent.tools.throttle import _reset
    _reset()
