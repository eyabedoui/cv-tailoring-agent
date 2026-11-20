
"""
Token estimation utilities for OpenAI and Groq API requests.

Token counts are estimates, not exact provider billing counts.
Unknown models are rejected instead of silently using an
arbitrary tokenizer.
"""

import json

import tiktoken


# Explicit tokenizer mapping for supported Groq models.
GROQ_TOKENIZERS = {
    "openai/gpt-oss-20b": "o200k_harmony",
    "openai/gpt-oss-120b": "o200k_harmony",
}


def _get_model_encoding(model: str):
    """
    Return the tokenizer for a supported model.

    Groq model identifiers use provider prefixes that may not
    be recognized by tiktoken.encoding_for_model().

    Unknown models remain blocked for budget safety.
    """

    if model in GROQ_TOKENIZERS:
        encoding_name = GROQ_TOKENIZERS[model]

        try:
            return tiktoken.get_encoding(encoding_name)
        except ValueError as exc:
            raise ValueError(
                f"Tokenizer {encoding_name} is not available "
                f"for model {model}. Update tiktoken."
            ) from exc

    try:
        return tiktoken.encoding_for_model(model)

    except KeyError as exc:
        raise ValueError(
            f"Unknown tokenizer for model: {model}. "
            "Cannot safely estimate API cost."
        ) from exc


def count_message_tokens(messages: list[dict], model: str) -> int:
    """
    Estimate input tokens in Chat Completions messages.

    Includes approximate message formatting overhead.

    This is not an exact count of provider-billed tokens,
    and must not be treated as a guaranteed spending cap.
    """

    encoding = _get_model_encoding(model)

    total_tokens = 0

    for message in messages:
        # Approximate message formatting overhead.
        total_tokens += 4

        for key, value in message.items():

            if isinstance(value, str):
                text = value
            else:
                text = json.dumps(
                    value,
                    ensure_ascii=False,
                )

            total_tokens += len(
                encoding.encode(text)
            )

    # Approximate assistant response prefix.
    total_tokens += 3

    return total_tokens
