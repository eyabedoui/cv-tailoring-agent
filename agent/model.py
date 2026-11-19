"""
OpenAI model adapter for the CV-tailoring agent.

Converts the loop's internal message/tool format to the OpenAI Chat Completions API
and parses the response back into the loop's dict protocol.
"""

import json
import os
import re
import time

from agent.config import MODEL_MAX_TOKENS, MAX_RETRIES_PER_TOOL, DEFAULT_OPENAI_MODEL
from agent.prompts import SYSTEM_PROMPT, JSON_PROTOCOL_PROMPT


# Patched in tests to avoid real sleeps during retry tests.
_sleep = time.sleep


class ModelUnavailableError(RuntimeError):
    """Raised when the OpenAI API cannot be reached after retries."""
    pass


class OpenAIModel:
    def __init__(self, model=None, client=None):
        self.model_id = model or os.environ.get("CV_AGENT_MODEL") or DEFAULT_OPENAI_MODEL
        # Set to True after the API rejects response_format; remembered across calls.
        self._skip_response_format = False

        if client is not None:
            self._client = client
            return

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY environment variable is not set. "
                "Add it to your .env file or export it before running."
            )

        try:
            import openai
            self._client = openai.OpenAI(api_key=api_key)
        except ImportError as exc:
            raise ImportError(
                "The 'openai' package is required. "
                "Run: pip install openai"
            ) from exc

    def call_model(self, messages: list[dict], tools: list[dict]) -> dict:
        """
        Call the OpenAI API and return a loop-protocol response dict.

        Returns one of:
            {"type": "tool_call", "tool_name": ..., "arguments": ..., "usage": ...}
            {"type": "final", "content": ..., "usage": ...}
            {"type": "invalid_response", "content": <raw>, "truncated": bool, "usage": ...}
        """
        system_prompt = SYSTEM_PROMPT.strip() + "\n\n" + JSON_PROTOCOL_PROMPT.strip()
        tool_descriptions = _format_tools(tools)
        if tool_descriptions:
            system_prompt += "\n\nAvailable tools:\n" + tool_descriptions

        # System message is first; _convert_messages adds user/assistant/tool turns.
        api_messages = [{"role": "system", "content": system_prompt}]
        api_messages.extend(_convert_messages(messages))

        response = self._call_with_retries(api_messages)

        choice = response.choices[0]
        raw = choice.message.content or ""
        finish_reason = choice.finish_reason

        usage = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        }

        if not raw or finish_reason == "length":
            return {
                "type": "invalid_response",
                "content": raw,
                "truncated": finish_reason == "length",
                "usage": usage,
            }

        parsed = _parse_response(raw)
        parsed["usage"] = usage
        return parsed

    def _call_with_retries(self, api_messages: list[dict]):
        """Call the API with retry logic for transient errors."""
        import openai

        delays = [1, 2]

        for attempt in range(MAX_RETRIES_PER_TOOL + 1):
            try:
                kwargs = {
                    "model": self.model_id,
                    "messages": api_messages,
                    "max_completion_tokens": MODEL_MAX_TOKENS,
                }
                if not self._skip_response_format:
                    kwargs["response_format"] = {"type": "json_object"}

                return self._client.chat.completions.create(**kwargs)

            except openai.BadRequestError as exc:
                if not self._skip_response_format and "response_format" in str(exc).lower():
                    # Retry once without it; remember the choice for future calls.
                    self._skip_response_format = True
                    continue
                raise ModelUnavailableError(
                    "OpenAI rejected the request. Check your inputs."
                ) from exc

            except openai.AuthenticationError as exc:
                # Never retry auth errors; never include the key in the message.
                raise ModelUnavailableError(
                    "OpenAI authentication failed. Check your OPENAI_API_KEY."
                ) from exc

            except (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.InternalServerError,
            ) as exc:
                if attempt < MAX_RETRIES_PER_TOOL:
                    _sleep(delays[min(attempt, len(delays) - 1)])
                    continue
                raise ModelUnavailableError(
                    "OpenAI API unavailable after retries. "
                    "Check your connection and rate limits."
                ) from exc

        raise ModelUnavailableError("OpenAI API unavailable after retries.")


# ---------------------------------------------------------------------------
# Helpers (shared across model adapters)
# ---------------------------------------------------------------------------

def _format_tools(tools: list[dict]) -> str:
    """Format tool schemas into a plain-text description."""
    lines = []
    for tool in tools:
        name = tool.get("name", "")
        desc = tool.get("description", "")
        # Accept both {"parameters": {...}} and {"input_schema": {...}}
        params = tool.get("input_schema") or tool.get("parameters") or {}
        lines.append(f"- {name}: {desc}")
        if params:
            lines.append(f"  parameters: {json.dumps(params)}")
    return "\n".join(lines)


def _convert_messages(messages: list[dict]) -> list[dict]:
    """
    Convert loop messages to Chat Completions API format.

    Loop roles:
        system    -> excluded here; the caller adds the system prompt as the first message
        assistant -> assistant
        user      -> user
        tool      -> user (the untrusted wrapper is already applied by loop.py)

    Consecutive messages with the same role are merged into one.

    Both OpenAI and Anthropic require the first non-system message to be from the
    user.  If the resulting list is empty or starts with an assistant message, a
    synthetic user message ("Start the task.") is prepended.
    """
    api_messages = []

    for msg in messages:
        role = msg.get("role")

        if role == "system":
            continue  # absorbed into the caller's system prompt

        if role == "assistant":
            api_role = "assistant"
            content = msg.get("content", "")
        elif role in ("tool", "user"):
            api_role = "user"
            content = msg.get("content", "")
        else:
            continue

        if api_messages and api_messages[-1]["role"] == api_role:
            # Merge consecutive same-role messages.
            api_messages[-1]["content"] += "\n" + content
        else:
            api_messages.append({"role": api_role, "content": content})

    if not api_messages or api_messages[0]["role"] != "user":
        api_messages.insert(0, {"role": "user", "content": "Start the task."})

    return api_messages


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}", re.DOTALL)


def _parse_response(raw: str) -> dict:
    """
    Robustly extract a JSON object from the model's raw text reply.

    Strategy:
    1. Strip code fences if present.
    2. Find the first {...} object in the text.
    3. If JSON parsing fails, return an invalid_response dict.
    """
    text = raw.strip()

    # 1. Strip code fences.
    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    # 2. Extract the first JSON object.
    obj_match = _JSON_OBJECT_RE.search(text)
    if not obj_match:
        return {"type": "invalid_response", "content": raw}

    try:
        parsed = json.loads(obj_match.group())
    except json.JSONDecodeError:
        return {"type": "invalid_response", "content": raw}

    if not isinstance(parsed, dict):
        return {"type": "invalid_response", "content": raw}

    return parsed
