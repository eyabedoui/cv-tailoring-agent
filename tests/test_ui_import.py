"""
Smoke-import tests for the UI modules.

test_logic_imports — always runs (no Chainlit needed).
test_app_imports   — skipped if chainlit is not installed.
"""

import importlib
import pytest


def test_logic_imports():
    mod = importlib.import_module("ui.logic")
    assert hasattr(mod, "render_untrusted")
    assert hasattr(mod, "map_tool_error")
    assert hasattr(mod, "format_stop_message")
    assert hasattr(mod, "format_status_line")
    assert hasattr(mod, "parse_slash_command")
    assert hasattr(mod, "get_output_files")
    assert hasattr(mod, "APPROVAL_PENDING_REPLY")


def test_app_imports():
    pytest.importorskip("chainlit")
    mod = importlib.import_module("ui.app")
    # The module must expose the Chainlit lifecycle handlers
    assert hasattr(mod, "on_chat_start")
    assert hasattr(mod, "on_message")
