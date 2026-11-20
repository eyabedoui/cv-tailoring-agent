
"""
OpenAI model adapter for the CV-tailoring agent.

Converts the loop's internal message/tool format to the OpenAI Chat
Completions API and parses the response back into the loop's dict protocol.
"""

import json
import os
import re
import time

from agent.config import (
    MODEL_MAX_TOKENS,
    MAX_RETRIES_PER_TOOL,
    DEFAULT_OPENAI_MODEL,
)
from agent.prompts import SYSTEM_PROMPT, JSON_PROTOCOL_PROMPT
from agent.budget import BudgetExceededError
from agent.costs import calculate_token_cost, estimate_request_cost


# Patched in tests to avoid real sleeps during retry tests.
_sleep = time.sleep


class ModelUnavailableError(RuntimeError):
    """Raised when the OpenAI API cannot be reached after retries."""
    pass


class OpenAIModel:
    def __init__(self, model=None, client=None, budget=None):
        self.model_id = (
            model
            or os.environ.get("CV_AGENT_MODEL")
            or DEFAULT_OPENAI_MODEL
        )
        self.budget = budget

        # Set to True after the API rejects response_format.
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
            {"type": "invalid_response", "content": ..., "truncated": bool, "usage": ...}
        """
        system_prompt = (
            SYSTEM_PROMPT.strip()
            + "\n\n"
            + JSON_PROTOCOL_PROMPT.strip()
        )
        tool_descriptions = _format_tools(tools)

        if tool_descriptions:
            system_prompt += (
                "\n\nAvailable tools:\n" + tool_descriptions
            )

        # System message is first.
        api_messages = [
            {"role": "system", "content": system_prompt}
        ]
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
                    kwargs["response_format"] = {
                        "type": "json_object"
                    }

                estimated_cost = None

                # --------------------------------------------------
                # API budget and pricing safety checks
                # --------------------------------------------------
                if self.budget is not None:
                    # Preserve the zero-budget protection.
                    if self.budget.remaining_usd <= 0:
                        raise BudgetExceededError(
                            "API budget exceeded. "
                            "Paid request blocked."
                        )

                    from agent.config import (
                        PRICE_PER_MTOK_INPUT,
                        PRICE_PER_MTOK_OUTPUT,
                    )

                    # Missing pricing must block paid requests.
                    if (
                        PRICE_PER_MTOK_INPUT <= 0
                        or PRICE_PER_MTOK_OUTPUT <= 0
                    ):
                        raise ValueError(
                            "API pricing is not configured. "
                            "Paid requests are blocked."
                        )

                    # Estimate cost before making the request.
                    estimated_cost = estimate_request_cost(
                        messages=api_messages,
                        model=self.model_id,
                        max_output_tokens=MODEL_MAX_TOKENS,
                        input_price_per_mtok=PRICE_PER_MTOK_INPUT,
                        output_price_per_mtok=PRICE_PER_MTOK_OUTPUT,
                    )

                    # Reserve the estimated cost.
                    self.budget.reserve(estimated_cost)

                response = self._client.chat.completions.create(
                    **kwargs
                )

                # --------------------------------------------------
                # Actual API cost settlement
                # --------------------------------------------------
                if self.budget is not None:
                    if response.usage is None:
                        raise ModelUnavailableError(
                            "OpenAI returned no usage information. "
                            "The budget reservation is retained."
                        )

                    actual_cost = calculate_token_cost(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        input_price_per_mtok=PRICE_PER_MTOK_INPUT,
                        output_price_per_mtok=PRICE_PER_MTOK_OUTPUT,
                    )

                    self.budget.settle(
                        reserved_cost_usd=estimated_cost,
                        actual_cost_usd=actual_cost,
                    )

                return response

            except openai.BadRequestError as exc:
                if (
                    not self._skip_response_format
                    and "response_format" in str(exc).lower()
                ):
                    # Retry without response_format.
                    self._skip_response_format = True
                    continue

                raise ModelUnavailableError(
                    "OpenAI rejected the request. "
                    "Check your inputs."
                ) from exc

            except openai.AuthenticationError as exc:
                # Never retry authentication errors.
                raise ModelUnavailableError(
                    "OpenAI authentication failed. "
                    "Check your OPENAI_API_KEY."
                ) from exc

            except openai.RateLimitError as exc:
                # Quota and billing errors are non-retryable.
                err_code = getattr(exc, "code", None) or ""
                err_body = str(exc).lower()

                if (
                    err_code == "insufficient_quota"
                    or any(
                        keyword in err_body
                        for keyword in (
                            "insufficient_quota",
                            "credits",
                            "quota",
                            "billing",
                        )
                    )
                ):
                    raise ModelUnavailableError(
                        "OpenAI account has no credits or quota left. "
                        "Add credits in the OpenAI billing settings, "
                        "then try again."
                    ) from exc

                if attempt < MAX_RETRIES_PER_TOOL:
                    _sleep(
                        delays[
                            min(attempt, len(delays) - 1)
                        ]
                    )
                    continue

                raise ModelUnavailableError(
                    "OpenAI API unavailable after retries. "
                    "Check your connection and rate limits."
                ) from exc

            except (
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.InternalServerError,
            ) as exc:
                if attempt < MAX_RETRIES_PER_TOOL:
                    _sleep(
                        delays[
                            min(attempt, len(delays) - 1)
                        ]
                    )
                    continue

                raise ModelUnavailableError(
                    "OpenAI API unavailable after retries. "
                    "Check your connection and rate limits."
                ) from exc

        raise ModelUnavailableError(
            "OpenAI API unavailable after retries."
        )


# ---------------------------------------------------------------------------
# Helpers (shared across model adapters)
# ---------------------------------------------------------------------------

def _format_tools(tools: list[dict]) -> str:
    """Format tool schemas into a plain-text description."""
    lines = []

    for tool in tools:
        name = tool.get("name", "")
        desc = tool.get("description", "")

        # Accept both supported schema formats.
        params = (
            tool.get("input_schema")
            or tool.get("parameters")
            or {}
        )

        lines.append(f"- {name}: {desc}")

        if params:
            lines.append(
                f"  parameters: {json.dumps(params)}"
            )

    return "\n".join(lines)


def _convert_messages(messages: list[dict]) -> list[dict]:
    """
    Convert loop messages to Chat Completions API format.

    Loop roles:
        system    -> excluded
        assistant -> assistant
        user      -> user
        tool      -> user

    Consecutive messages with the same role are merged.
    """
    api_messages = []

    for msg in messages:
        role = msg.get("role")

        if role == "system":
            continue

        if role == "assistant":
            api_role = "assistant"
            content = msg.get("content", "")

        elif role in ("tool", "user"):
            api_role = "user"
            content = msg.get("content", "")

        else:
            continue

        if (
            api_messages
            and api_messages[-1]["role"] == api_role
        ):
            api_messages[-1]["content"] += (
                "\n" + content
            )
        else:
            api_messages.append({
                "role": api_role,
                "content": content,
            })

    if (
        not api_messages
        or api_messages[0]["role"] != "user"
    ):
        api_messages.insert(
            0,
            {
                "role": "user",
                "content": "Start the task.",
            },
        )

    return api_messages


_CODE_FENCE_RE = re.compile(
    r"```(?:json)?\s*([\s\S]*?)\s*```",
    re.IGNORECASE,
)

_JSON_OBJECT_RE = re.compile(
    r"\{[\s\S]*\}",
    re.DOTALL,
)


def _parse_response(raw: str) -> dict:
    """
    Extract a JSON object from the model's raw response.

    1. Strip code fences.
    2. Find the JSON object.
    3. Parse JSON.
    4. Return invalid_response if parsing fails.
    """
    text = raw.strip()

    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    obj_match = _JSON_OBJECT_RE.search(text)

    if not obj_match:
        return {
            "type": "invalid_response",
            "content": raw,
        }

    try:
        parsed = json.loads(obj_match.group())
    except json.JSONDecodeError:
        return {
            "type": "invalid_response",
            "content": raw,
        }

    if not isinstance(parsed, dict):
        return {
            "type": "invalid_response",
            "content": raw,
        }

    return parsed
