"""
Tests for the smoke_web command (sandbox/manage.py).

smoke_web is a MANUAL integration test; pytest must never call real clients.
These tests verify:
  - smoke_web raises SystemExit(1) when API keys are missing
  - The command is not accidentally invoked by any pytest fixture or autouse
"""

import pytest


def test_smoke_web_aborts_when_openai_key_missing(monkeypatch):
    """smoke_web must sys.exit(1) when OPENAI_API_KEY is not set."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    from sandbox.manage import smoke_web
    with pytest.raises(SystemExit) as exc_info:
        smoke_web()
    assert exc_info.value.code == 1


def test_smoke_web_aborts_when_firecrawl_key_missing(monkeypatch):
    """smoke_web must sys.exit(1) when FIRECRAWL_API_KEY is not set."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-present")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    from sandbox.manage import smoke_web
    with pytest.raises(SystemExit) as exc_info:
        smoke_web()
    assert exc_info.value.code == 1


def test_smoke_web_aborts_when_both_keys_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    from sandbox.manage import smoke_web
    with pytest.raises(SystemExit) as exc_info:
        smoke_web()
    assert exc_info.value.code == 1


def test_smoke_web_exit_message_names_missing_keys(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    from sandbox.manage import smoke_web
    with pytest.raises(SystemExit):
        smoke_web()
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.out
    assert "FIRECRAWL_API_KEY" in captured.out


def test_smoke_web_is_not_called_by_any_fixture():
    """Verify smoke_web is not wired into conftest or autouse fixtures."""
    from pathlib import Path
    conftest_src = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")
    assert "smoke_web" not in conftest_src
