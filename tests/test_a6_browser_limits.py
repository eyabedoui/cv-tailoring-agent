"""A6 — Verify configured Browser Use execution limits."""

from pathlib import Path
import re


CLIENTS_FILE = (
    Path(__file__).resolve().parents[1]
    / "agent"
    / "tools"
    / "clients.py"
)


def test_browser_search_step_limit():
    source = CLIENTS_FILE.read_text(encoding="utf-8")

    assert re.search(
        r"agent\.run\(\s*max_steps\s*=\s*20\s*,\s*timeout\s*=\s*120\s*\)",
        source,
    )


def test_browser_submission_step_limit():
    source = CLIENTS_FILE.read_text(encoding="utf-8")

    assert re.search(
        r"agent\.run\(\s*max_steps\s*=\s*10\s*,\s*timeout\s*=\s*60\s*\)",
        source,
    )