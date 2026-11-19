"""
Tests for agent/model.py (OpenAI adapter) and helpers.
"""

import sys
import json
import unittest.mock as mock

import pytest

from agent.model import OpenAIModel, ModelUnavailableError, _parse_response, _convert_messages, _format_tools
from agent.__main__ import main as agent_main, FAKE_WALKTHROUGH_RESPONSES


# ---------------------------------------------------------------------------
# Fake openai module injected for all tests in this file.
# Using real openai exception constructors requires httpx.Response objects, so
# we provide lightweight stand-ins patched into sys.modules.
# ---------------------------------------------------------------------------

class _FakeBadRequestError(Exception):
    pass

class _FakeAuthenticationError(Exception):
    pass

class _FakeRateLimitError(Exception):
    pass

class _FakeAPIConnectionError(Exception):
    pass

class _FakeAPITimeoutError(Exception):
    pass

class _FakeInternalServerError(Exception):
    pass


class _FakeOpenAIModule:
    BadRequestError = _FakeBadRequestError
    AuthenticationError = _FakeAuthenticationError
    RateLimitError = _FakeRateLimitError
    APIConnectionError = _FakeAPIConnectionError
    APITimeoutError = _FakeAPITimeoutError
    InternalServerError = _FakeInternalServerError

    class OpenAI:
        def __init__(self, api_key=None):
            self.chat = mock.MagicMock()


_FAKE_OPENAI = _FakeOpenAIModule()


@pytest.fixture(autouse=True)
def _patch_openai_module():
    """Replace sys.modules['openai'] with the fake for every test in this file."""
    with mock.patch.dict(sys.modules, {"openai": _FAKE_OPENAI}):
        yield _FAKE_OPENAI


# ---------------------------------------------------------------------------
# Helper: build a mock OpenAI completion response
# ---------------------------------------------------------------------------

def _make_response(content, finish_reason="stop", prompt_tokens=42, completion_tokens=17):
    usage = mock.MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    message = mock.MagicMock()
    message.content = content

    choice = mock.MagicMock()
    choice.message = message
    choice.finish_reason = finish_reason

    response = mock.MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _ok_response():
    return _make_response('{"type": "final", "content": "done"}')


# ---------------------------------------------------------------------------
# _parse_response unit tests (unchanged from previous session)
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
# OpenAIModel: missing API key raises EnvironmentError
# ---------------------------------------------------------------------------

def test_openai_model_raises_on_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
        OpenAIModel()


def test_openai_model_raises_on_missing_package(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with mock.patch.dict(sys.modules, {"openai": None}):
        with pytest.raises(ImportError, match="openai"):
            OpenAIModel()


# ---------------------------------------------------------------------------
# OpenAIModel: system message is first; no temperature/max_tokens
# ---------------------------------------------------------------------------

def test_system_message_is_first_api_message():
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = _ok_response()

    model = OpenAIModel(client=mock_client)
    model.call_model([], [])

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["messages"][0]["role"] == "system"


def test_system_message_contains_prompts():
    from agent.prompts import SYSTEM_PROMPT, JSON_PROTOCOL_PROMPT
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = _ok_response()

    model = OpenAIModel(client=mock_client)
    model.call_model([], [])

    sys_content = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert SYSTEM_PROMPT.strip()[:30] in sys_content
    assert JSON_PROTOCOL_PROMPT.strip()[:30] in sys_content


def test_no_temperature_or_max_tokens_sent():
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = _ok_response()

    model = OpenAIModel(client=mock_client)
    model.call_model([], [])

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "temperature" not in kwargs
    assert "max_tokens" not in kwargs


def test_max_completion_tokens_equals_model_max_tokens():
    from agent.config import MODEL_MAX_TOKENS
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = _ok_response()

    model = OpenAIModel(client=mock_client)
    model.call_model([], [])

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["max_completion_tokens"] == MODEL_MAX_TOKENS


# ---------------------------------------------------------------------------
# OpenAIModel: response_format json_object; fallback and remembered
# ---------------------------------------------------------------------------

def test_response_format_json_object_sent_initially():
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = _ok_response()

    model = OpenAIModel(client=mock_client)
    model.call_model([], [])

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs.get("response_format") == {"type": "json_object"}


def test_response_format_fallback_on_bad_request():
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _FakeBadRequestError("model does not support response_format"),
        _ok_response(),
    ]

    model = OpenAIModel(client=mock_client)
    result = model.call_model([], [])

    assert result["type"] == "final"
    assert model._skip_response_format is True
    assert mock_client.chat.completions.create.call_count == 2
    # Second call must not carry response_format
    second_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
    assert "response_format" not in second_kwargs


def test_response_format_fallback_remembered_across_calls():
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = _ok_response()

    model = OpenAIModel(client=mock_client)
    model._skip_response_format = True  # already remembered

    model.call_model([], [])
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "response_format" not in kwargs


# ---------------------------------------------------------------------------
# OpenAIModel: usage mapping
# ---------------------------------------------------------------------------

def test_usage_maps_prompt_to_input_completion_to_output():
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = _make_response(
        '{"type": "final", "content": "done"}',
        prompt_tokens=99,
        completion_tokens=33,
    )

    model = OpenAIModel(client=mock_client)
    result = model.call_model([], [])

    assert result["usage"]["input_tokens"] == 99
    assert result["usage"]["output_tokens"] == 33


# ---------------------------------------------------------------------------
# OpenAIModel: finish_reason == "length" and empty content
# ---------------------------------------------------------------------------

def test_finish_reason_length_gives_invalid_response_truncated():
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = _make_response(
        '{"type": "final"', finish_reason="length"
    )

    model = OpenAIModel(client=mock_client)
    result = model.call_model([], [])

    assert result["type"] == "invalid_response"
    assert result["truncated"] is True


def test_empty_content_gives_invalid_response_not_truncated():
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = _make_response(
        None, finish_reason="stop"
    )

    model = OpenAIModel(client=mock_client)
    result = model.call_model([], [])

    assert result["type"] == "invalid_response"
    assert result["truncated"] is False


# ---------------------------------------------------------------------------
# OpenAIModel: transient errors — retry then succeed; exhausted → ModelUnavailableError
# ---------------------------------------------------------------------------

def test_transient_error_then_success(monkeypatch):
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _FakeRateLimitError("rate limit"),
        _ok_response(),
    ]

    sleep_calls = []
    monkeypatch.setattr("agent.model._sleep", lambda s: sleep_calls.append(s))

    model = OpenAIModel(client=mock_client)
    result = model.call_model([], [])

    assert result["type"] == "final"
    assert sleep_calls == [1]


def test_transient_errors_exhausted_raise_model_unavailable(monkeypatch):
    from agent.config import MAX_RETRIES_PER_TOOL

    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.side_effect = _FakeRateLimitError("rate limit")

    sleep_calls = []
    monkeypatch.setattr("agent.model._sleep", lambda s: sleep_calls.append(s))

    model = OpenAIModel(client=mock_client)
    with pytest.raises(ModelUnavailableError):
        model.call_model([], [])

    assert mock_client.chat.completions.create.call_count == MAX_RETRIES_PER_TOOL + 1
    assert sleep_calls == [1, 2]


def test_connection_error_is_retried(monkeypatch):
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _FakeAPIConnectionError("connection failed"),
        _ok_response(),
    ]

    sleep_calls = []
    monkeypatch.setattr("agent.model._sleep", lambda s: sleep_calls.append(s))

    model = OpenAIModel(client=mock_client)
    result = model.call_model([], [])

    assert result["type"] == "final"
    assert len(sleep_calls) == 1


def test_server_error_is_retried(monkeypatch):
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _FakeInternalServerError("500"),
        _ok_response(),
    ]

    sleep_calls = []
    monkeypatch.setattr("agent.model._sleep", lambda s: sleep_calls.append(s))

    model = OpenAIModel(client=mock_client)
    result = model.call_model([], [])

    assert result["type"] == "final"


# ---------------------------------------------------------------------------
# OpenAIModel: auth error raises immediately; message does not contain the key
# ---------------------------------------------------------------------------

def test_auth_error_raises_model_unavailable_immediately(monkeypatch):
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.side_effect = _FakeAuthenticationError("bad key")

    sleep_calls = []
    monkeypatch.setattr("agent.model._sleep", lambda s: sleep_calls.append(s))

    model = OpenAIModel(client=mock_client)
    with pytest.raises(ModelUnavailableError):
        model.call_model([], [])

    assert sleep_calls == []  # no sleep — raised immediately
    assert mock_client.chat.completions.create.call_count == 1


def test_auth_error_message_does_not_contain_api_key(monkeypatch):
    fake_key = "sk-test-secret-99999"
    monkeypatch.setenv("OPENAI_API_KEY", fake_key)

    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.side_effect = _FakeAuthenticationError(fake_key)

    model = OpenAIModel(client=mock_client)
    with pytest.raises(ModelUnavailableError) as exc_info:
        model.call_model([], [])

    assert fake_key not in str(exc_info.value)


# ---------------------------------------------------------------------------
# OpenAIModel: bad JSON reply → invalid_response with usage
# ---------------------------------------------------------------------------

def test_bad_reply_returns_invalid_response_with_usage():
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = _make_response(
        "I cannot understand this.", prompt_tokens=5, completion_tokens=3
    )

    model = OpenAIModel(client=mock_client)
    result = model.call_model([], [])

    assert result["type"] == "invalid_response"
    assert result["usage"]["input_tokens"] == 5
    assert result["usage"]["output_tokens"] == 3


# ---------------------------------------------------------------------------
# OpenAIModel: protocol conversion — system not in converted turns; user kept
# ---------------------------------------------------------------------------

def test_protocol_conversion_user_in_turns():
    mock_client = mock.MagicMock()
    mock_client.chat.completions.create.return_value = _make_response(
        '{"type": "tool_call", "tool_name": "read_master_cv", "arguments": {}}'
    )

    model = OpenAIModel(client=mock_client)
    messages = [
        {"role": "system", "content": "You are an agent."},
        {"role": "user", "content": "My task."},
        {"role": "assistant", "content": '{"type":"tool_call","tool_name":"x","arguments":{}}'},
        {"role": "tool", "name": "x", "content": "<tool_result>ok</tool_result>"},
    ]
    result = model.call_model(messages, [])

    assert result["type"] == "tool_call"
    api_msgs = mock_client.chat.completions.create.call_args.kwargs["messages"]
    # First message is system (from call_model), remaining from _convert_messages
    assert api_msgs[0]["role"] == "system"
    # The loop-system message is excluded from _convert_messages; user is present
    roles = [m["role"] for m in api_msgs[1:]]
    assert "user" in roles


# ---------------------------------------------------------------------------
# End-to-end: python -m agent --model fake --auto-approve
# ---------------------------------------------------------------------------

def test_main_fake_auto_approve(tmp_path, monkeypatch):
    # Redirect cwd so logs go to tmp_path.
    monkeypatch.chdir(tmp_path)

    result = agent_main(["--model", "fake", "--auto-approve"])

    assert result["stop_reason"] == "done"
    assert result["step_count"] == len(FAKE_WALKTHROUGH_RESPONSES) - 1  # final is not a step
    assert "submitted" in result["answer"].lower() or result["answer"]


# ---------------------------------------------------------------------------
# OpenAIModel: quota 429 raises immediately; non-quota 429 is retried
# ---------------------------------------------------------------------------

def test_quota_error_by_code_raises_model_unavailable_immediately(monkeypatch):
    mock_client = mock.MagicMock()
    err = _FakeRateLimitError("insufficient_quota")
    err.code = "insufficient_quota"
    mock_client.chat.completions.create.side_effect = err

    sleep_calls = []
    monkeypatch.setattr("agent.model._sleep", lambda s: sleep_calls.append(s))

    model = OpenAIModel(client=mock_client)
    with pytest.raises(ModelUnavailableError, match="credits"):
        model.call_model([], [])

    assert sleep_calls == []  # No retries for quota errors
    assert mock_client.chat.completions.create.call_count == 1


def test_quota_error_by_message_keyword_raises_immediately(monkeypatch):
    mock_client = mock.MagicMock()
    # "billing" in the error message should trigger the quota path
    err = _FakeRateLimitError("You exceeded your current quota. Check your billing.")
    err.code = None
    mock_client.chat.completions.create.side_effect = err

    sleep_calls = []
    monkeypatch.setattr("agent.model._sleep", lambda s: sleep_calls.append(s))

    model = OpenAIModel(client=mock_client)
    with pytest.raises(ModelUnavailableError, match="credits"):
        model.call_model([], [])

    assert sleep_calls == []


def test_quota_error_message_mentions_billing_settings(monkeypatch):
    mock_client = mock.MagicMock()
    err = _FakeRateLimitError("insufficient_quota")
    err.code = "insufficient_quota"
    mock_client.chat.completions.create.side_effect = err

    model = OpenAIModel(client=mock_client)
    with pytest.raises(ModelUnavailableError) as exc_info:
        model.call_model([], [])

    msg = str(exc_info.value).lower()
    assert "billing" in msg or "credits" in msg


def test_non_quota_rate_limit_still_retried(monkeypatch):
    mock_client = mock.MagicMock()
    err = _FakeRateLimitError("rate limit exceeded, please slow down")
    err.code = None
    mock_client.chat.completions.create.side_effect = [err, _ok_response()]

    sleep_calls = []
    monkeypatch.setattr("agent.model._sleep", lambda s: sleep_calls.append(s))

    model = OpenAIModel(client=mock_client)
    result = model.call_model([], [])

    assert result["type"] == "final"
    assert sleep_calls  # Was retried with a sleep
