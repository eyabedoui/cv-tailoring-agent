"""
Tests for agent/__main__.py: CLI flags, .env loading, and walkthrough paths.
"""

import os
import unittest.mock as mock

import pytest

from agent.__main__ import main as agent_main, FAKE_WALKTHROUGH_RESPONSES, _load_dotenv
from agent.loop import AgentLoop
from agent.tools.writes import save_tailored_cv
from sandbox.portal import Portal


# ---------------------------------------------------------------------------
# main(["--model", "fake", "--auto-approve"]) finishes with stop_reason "done"
# ---------------------------------------------------------------------------

def test_main_fake_auto_approve_stop_reason(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = agent_main(["--model", "fake", "--auto-approve"])
    assert result["stop_reason"] == "done"


# ---------------------------------------------------------------------------
# --request replaces the generated message
# ---------------------------------------------------------------------------

def test_request_flag_replaces_generated_message(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    captured_messages = []

    original_run = AgentLoop.run

    def spy_run(self, initial_messages=None):
        captured_messages.extend(initial_messages or [])
        return original_run(self, initial_messages=initial_messages)

    monkeypatch.setattr(AgentLoop, "run", spy_run)

    custom = "My completely custom request text."
    agent_main(["--model", "fake", "--auto-approve", "--request", custom])

    assert any(m.get("content") == custom for m in captured_messages)


def test_request_flag_ignores_job_url(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    captured_messages = []

    original_run = AgentLoop.run

    def spy_run(self, initial_messages=None):
        captured_messages.extend(initial_messages or [])
        return original_run(self, initial_messages=initial_messages)

    monkeypatch.setattr(AgentLoop, "run", spy_run)

    agent_main([
        "--model", "fake",
        "--auto-approve",
        "--job-url", "mock://jobs/job_002",
        "--request", "Override request.",
    ])

    contents = [m.get("content", "") for m in captured_messages]
    assert any("Override request." in c for c in contents)
    assert not any("job_002" in c for c in contents)


def test_no_request_flag_uses_job_url(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    captured_messages = []

    original_run = AgentLoop.run

    def spy_run(self, initial_messages=None):
        captured_messages.extend(initial_messages or [])
        return original_run(self, initial_messages=initial_messages)

    monkeypatch.setattr(AgentLoop, "run", spy_run)

    agent_main([
        "--model", "fake",
        "--auto-approve",
        "--job-url", "mock://jobs/job_001",
    ])

    contents = [m.get("content", "") for m in captured_messages]
    assert any("mock://jobs/job_001" in c for c in contents)


# ---------------------------------------------------------------------------
# .env helper
# ---------------------------------------------------------------------------

def test_load_dotenv_sets_missing_variable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MY_TEST_KEY", raising=False)

    (tmp_path / ".env").write_text("MY_TEST_KEY=hello_world\n", encoding="utf-8")
    _load_dotenv()

    assert os.environ.get("MY_TEST_KEY") == "hello_world"


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MY_TEST_KEY2", "original")

    (tmp_path / ".env").write_text("MY_TEST_KEY2=overridden\n", encoding="utf-8")
    _load_dotenv()

    assert os.environ.get("MY_TEST_KEY2") == "original"


def test_load_dotenv_ignores_blank_lines_and_comments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOTENV_REAL", raising=False)

    (tmp_path / ".env").write_text(
        "# this is a comment\n"
        "\n"
        "DOTENV_REAL=value\n",
        encoding="utf-8",
    )
    _load_dotenv()

    assert os.environ.get("DOTENV_REAL") == "value"


def test_load_dotenv_strips_quotes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUOTED_KEY", raising=False)

    (tmp_path / ".env").write_text('QUOTED_KEY="my secret"\n', encoding="utf-8")
    _load_dotenv()

    assert os.environ.get("QUOTED_KEY") == "my secret"


def test_load_dotenv_no_file_does_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Ensure no .env file exists
    env_file = tmp_path / ".env"
    if env_file.exists():
        env_file.unlink()

    # Should not raise
    _load_dotenv()


# ---------------------------------------------------------------------------
# Fake walkthrough submit paths match save_tailored_cv output paths
# ---------------------------------------------------------------------------

def test_fake_walkthrough_cv_path_matches_save_tailored_cv(tmp_path):
    """FAKE_WALKTHROUGH_RESPONSES submit cv_path filename must match save_tailored_cv output."""
    import pathlib
    portal = Portal(sandbox_dir=str(tmp_path))

    submit_step = next(
        s for s in FAKE_WALKTHROUGH_RESPONSES
        if s.get("tool_name") == "submit_application"
    )
    save_cv_step = next(
        s for s in FAKE_WALKTHROUGH_RESPONSES
        if s.get("tool_name") == "save_tailored_cv"
        and s["arguments"].get("kind") == "cv"
    )

    args = save_cv_step["arguments"]
    result = save_tailored_cv(
        text=args["text"],
        job_id=args["job_id"],
        kind=args["kind"],
        _portal=portal,
    )
    assert not result.get("error"), f"save_tailored_cv failed: {result}"

    actual_name = pathlib.Path(result["path"]).name
    expected_name = pathlib.Path(submit_step["arguments"]["cv_path"]).name

    assert actual_name == expected_name, (
        f"cv_path in FAKE_WALKTHROUGH_RESPONSES has filename {expected_name!r} "
        f"but save_tailored_cv writes {actual_name!r}"
    )


# ---------------------------------------------------------------------------
# ModelUnavailableError: prints message and exits with code 2
# ---------------------------------------------------------------------------

def test_model_unavailable_exits_with_code_2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    from agent.model import ModelUnavailableError

    def _raise(self, *args, **kwargs):
        raise ModelUnavailableError("No credits available.")

    monkeypatch.setattr(AgentLoop, "run", _raise)

    with pytest.raises(SystemExit) as exc_info:
        agent_main(["--model", "fake", "--auto-approve"])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "Model unavailable" in captured.out
    assert "No credits available." in captured.out


def test_fake_walkthrough_cover_letter_path_matches_save_tailored_cv(tmp_path):
    """FAKE_WALKTHROUGH_RESPONSES cover_letter_path filename must match save_tailored_cv output."""
    import pathlib
    portal = Portal(sandbox_dir=str(tmp_path))

    submit_step = next(
        s for s in FAKE_WALKTHROUGH_RESPONSES
        if s.get("tool_name") == "submit_application"
    )
    save_cl_step = next(
        s for s in FAKE_WALKTHROUGH_RESPONSES
        if s.get("tool_name") == "save_tailored_cv"
        and s["arguments"].get("kind") == "cover_letter"
    )

    args = save_cl_step["arguments"]
    result = save_tailored_cv(
        text=args["text"],
        job_id=args["job_id"],
        kind=args["kind"],
        _portal=portal,
    )
    assert not result.get("error"), f"save_tailored_cv failed: {result}"

    actual_name = pathlib.Path(result["path"]).name
    expected_name = pathlib.Path(submit_step["arguments"]["cover_letter_path"]).name

    assert actual_name == expected_name, (
        f"cover_letter_path in FAKE_WALKTHROUGH_RESPONSES has filename {expected_name!r} "
        f"but save_tailored_cv writes {actual_name!r}"
    )
