
"""Tests for agent/model.py and agent/__main__.py — Item 6."""

import json
import os
import unittest.mock as mock

import pytest

from agent.model import AnthropicModel, _parse_response, _convert_messages, _format_tools
from agent.__main__ import main as agent_main, FAKE_WALKTHROUGH_RESPONSES


# ---------------------------------------------------------------------------
# _parse_response unit tests
# ---------------------------------------------------------------------------

def test_parse_plain_json_tool_call():
    raw = '{"type": "tool_call", "tool_name": "read_master_cv", "arguments": {}}'
    result = _parse_response(raw)
    assert result["type"] == "tool_call"
    assert result["tool_name"] == "read_master_cv"


def test_parse_plain_json_final():
    raw = '{"type": "final", "content": "Done."}'
    result = _parse_response(raw)
    assert result["type"] == "final"
    assert result["content"] == "Done."


def test_parse_strips_json_code_fence():
    raw = '```json\n{"type": "final", "content": "hi"}\n```'
    result = _parse_response(raw)
    assert result["type"] == "final"


def test_parse_strips_bare_code_fence():
    raw = '```\n{"type": "final", "content": "hi"}\n```'
    result = _parse_response(raw)
    assert result["type"] == "final"


def test_parse_extracts_json_from_prose():
    raw = 'Here is my answer: {"type": "final", "content": "done"} as requested.'
    result = _parse_response(raw)
    assert result["type"] == "final"


def test_parse_garbage_returns_invalid_response():
    raw = "I don't know what to do."
    result = _parse_response(raw)
    assert result["type"] == "invalid_response"
    assert result["content"] == raw


def test_parse_broken_json_returns_invalid_response():
    raw = '{"type": "final", "content": "oops"'
    result = _parse_response(raw)
    assert result["type"] == "invalid_response"


# ---------------------------------------------------------------------------
# _convert_messages unit tests
# ---------------------------------------------------------------------------

def test_convert_skips_system_messages():
    messages = [
        {"role": "system", "content": "You are a CV agent."},
        {"role": "assistant", "content": "I will help."},
    ]
    api = _convert_messages(messages)
    # system is excluded; since no user precedes the assistant, "Start the task." is prepended
    assert all(m["role"] != "system" for m in api)
    assert api[0]["role"] == "user"
    assert api[-1]["role"] == "assistant"


def test_convert_tool_becomes_user():
    messages = [
        {"role": "tool", "name": "read_master_cv", "content": "<tool_result>...</tool_result>"},
    ]
    api = _convert_messages(messages)
    assert api[0]["role"] == "user"


def test_convert_merges_consecutive_same_role():
    messages = [
        {"role": "tool", "name": "a", "content": "first"},
        {"role": "tool", "name": "b", "content": "second"},
    ]
    api = _convert_messages(messages)
    assert len(api) == 1
    assert "first" in api[0]["content"]
    assert "second" in api[0]["content"]


def test_convert_does_not_merge_different_roles():
    messages = [
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": "step 1"},
        {"role": "tool", "name": "x", "content": "result"},
    ]
    api = _convert_messages(messages)
    # user, assistant, user(tool) — three distinct role-changes, no merging
    assert len(api) == 3


def test_convert_user_message_is_kept():
    messages = [
        {"role": "user", "content": "Please tailor my CV."},
    ]
    api = _convert_messages(messages)
    assert len(api) == 1
    assert api[0]["role"] == "user"
    assert api[0]["content"] == "Please tailor my CV."


def test_convert_user_message_is_first():
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "My task."},
        {"role": "assistant", "content": "step 1"},
    ]
    api = _convert_messages(messages)
    assert api[0]["role"] == "user"


def test_convert_prepends_start_task_when_first_is_assistant():
    messages = [
        {"role": "assistant", "content": "I will start."},
        {"role": "tool", "name": "x", "content": "result"},
    ]
    api = _convert_messages(messages)
    assert api[0]["role"] == "user"
    assert api[0]["content"] == "Start the task."


def test_convert_prepends_start_task_for_empty_input():
    api = _convert_messages([])
    assert len(api) == 1
    assert api[0] == {"role": "user", "content": "Start the task."}


def test_convert_prepends_start_task_for_system_only():
    messages = [{"role": "system", "content": "prompt"}]
    api = _convert_messages(messages)
    assert api[0] == {"role": "user", "content": "Start the task."}


def test_convert_merges_user_and_tool_into_user():
    messages = [
        {"role": "user", "content": "task"},
        {"role": "tool", "name": "x", "content": "result"},
    ]
    api = _convert_messages(messages)
    assert len(api) == 1
    assert api[0]["role"] == "user"
    assert "task" in api[0]["content"]
    assert "result" in api[0]["content"]


# ---------------------------------------------------------------------------
# max_tokens uses MODEL_MAX_TOKENS
# ---------------------------------------------------------------------------

def test_max_tokens_equals_model_max_tokens(monkeypatch):
    from agent.config import MODEL_MAX_TOKENS

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_response = _make_mock_response('{"type": "final", "content": "done"}')

    with mock.patch("anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.return_value = mock_response

        model = AnthropicModel(model="claude-haiku-4-5")
        model.call_model([], [])

    call_kwargs = instance.messages.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == MODEL_MAX_TOKENS


# ---------------------------------------------------------------------------
# _format_tools unit tests
# ---------------------------------------------------------------------------

def test_format_tools_basic():
    tools = [{"name": "read_master_cv", "description": "Reads the CV.", "parameters": {}}]
    text = _format_tools(tools)
    assert "read_master_cv" in text


def test_format_tools_accepts_input_schema():
    tools = [{"name": "t", "description": "d", "input_schema": {"url": "string"}}]
    text = _format_tools(tools)
    assert "url" in text


# ---------------------------------------------------------------------------
# AnthropicModel: missing API key raises clearly
# ---------------------------------------------------------------------------

def test_anthropic_model_raises_on_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
        AnthropicModel()


# ---------------------------------------------------------------------------
# AnthropicModel: usage passthrough with mocked client
# ---------------------------------------------------------------------------

def _make_mock_response(text, input_tokens=42, output_tokens=17):
    usage = mock.MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens

    content_block = mock.MagicMock()
    content_block.text = text

    response = mock.MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


def test_anthropic_model_usage_passthrough(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_response = _make_mock_response(
        '{"type": "final", "content": "done"}',
        input_tokens=42,
        output_tokens=17,
    )

    with mock.patch("anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.return_value = mock_response

        model = AnthropicModel(model="claude-haiku-4-5")
        result = model.call_model([], [])

    assert result["usage"]["input_tokens"] == 42
    assert result["usage"]["output_tokens"] == 17
    assert result["type"] == "final"


def test_anthropic_model_protocol_conversion(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_response = _make_mock_response(
        '{"type": "tool_call", "tool_name": "read_master_cv", "arguments": {}}'
    )

    with mock.patch("anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.return_value = mock_response

        model = AnthropicModel()
        messages = [
            {"role": "system", "content": "You are an agent."},
            {"role": "assistant", "content": '{"type":"tool_call","tool_name":"x","arguments":{}}'},
            {"role": "tool", "name": "x", "content": "<tool_result>ok</tool_result>"},
        ]
        result = model.call_model(messages, [])

    assert result["type"] == "tool_call"
    # Check that the API was called with correctly converted messages.
    call_kwargs = instance.messages.create.call_args.kwargs
    api_msgs = call_kwargs["messages"]
    # system message must be excluded; consecutive same-role merging is optional here
    roles = [m["role"] for m in api_msgs]
    assert "system" not in roles


def test_anthropic_model_bad_reply_returns_invalid_response(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_response = _make_mock_response("I cannot understand this request.")

    with mock.patch("anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.return_value = mock_response

        model = AnthropicModel()
        result = model.call_model([], [])

    assert result["type"] == "invalid_response"
    assert "usage" in result


# ---------------------------------------------------------------------------
# End-to-end: python -m agent --model fake --auto-approve
# ---------------------------------------------------------------------------

def test_main_fake_auto_approve(tmp_path, monkeypatch):
    # Redirect logs so we don't pollute the real logs/ dir.
    monkeypatch.chdir(tmp_path)

    result = agent_main(["--model", "fake", "--auto-approve"])

    assert result["stop_reason"] == "done"
    assert result["step_count"] == len(FAKE_WALKTHROUGH_RESPONSES) - 1  # final is not a step
    assert "submitted" in result["answer"].lower() or result["answer"]
