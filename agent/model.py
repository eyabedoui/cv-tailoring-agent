
"""
Real Anthropic model adapter for the CV-tailoring agent.

Converts the loop's internal message/tool format to the Anthropic Messages API
and parses the response back into the loop's dict protocol.
"""

import json
import os
import re

from agent.prompts import SYSTEM_PROMPT, JSON_PROTOCOL_PROMPT
from agent.untrusted import wrap_untrusted


class AnthropicModel:
    def __init__(self, model=None):
        self.model_id = model or os.environ.get(
            "CV_AGENT_MODEL", "claude-haiku-4-5"
        )

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Add it to your .env file or export it before running."
            )

        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required. "
                "Run: pip install anthropic"
            ) from exc

    def call_model(self, messages: list[dict], tools: list[dict]) -> dict:
        """
        Call the Anthropic API and return a loop-protocol response dict.

        Returns one of:
            {"type": "tool_call", "tool_name": ..., "arguments": ..., "usage": ...}
            {"type": "final", "content": ..., "usage": ...}
            {"type": "invalid_response", "content": <raw text>, "usage": ...}
        """
        system_prompt = SYSTEM_PROMPT.strip() + "\n\n" + JSON_PROTOCOL_PROMPT.strip()
        tool_descriptions = _format_tools(tools)
        if tool_descriptions:
            system_prompt += "\n\nAvailable tools:\n" + tool_descriptions

        api_messages = _convert_messages(messages)

        response = self._client.messages.create(
            model=self.model_id,
            max_tokens=1024,
            system=system_prompt,
            messages=api_messages,
        )

        raw = response.content[0].text if response.content else ""
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        parsed = _parse_response(raw)
        parsed["usage"] = usage
        return parsed


# ---------------------------------------------------------------------------
# Helpers
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
    Convert loop messages to Anthropic API message format.

    Loop roles:
        system   -> absorbed into system prompt (skipped here)
        assistant -> assistant
        tool     -> user (the untrusted wrapper is already applied by loop.py)

    Consecutive messages with the same role are merged into one.
    """
    api_messages = []

    for msg in messages:
        role = msg.get("role")

        if role == "system":
            continue  # already in system prompt

        if role == "assistant":
            api_role = "assistant"
            content = msg.get("content", "")
        elif role == "tool":
            api_role = "user"
            content = msg.get("content", "")
        else:
            continue

        if api_messages and api_messages[-1]["role"] == api_role:
            # Merge consecutive same-role messages.
            api_messages[-1]["content"] += "\n" + content
        else:
            api_messages.append({"role": api_role, "content": content})

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
