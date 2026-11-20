
"""
Token estimation utilities for OpenAI API requests.
"""

import json

import tiktoken


def count_message_tokens(messages: list[dict], model: str) -> int:
    """
    Estimate the number of input tokens in Chat Completions messages.

    This is an estimate, not an exact billing count.
    """

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        raise ValueError(
            f"Unknown tokenizer for model: {model}. "
            "Cannot safely estimate API cost."
        )

    total_tokens = 0

    for message in messages:
        # Approximate message formatting overhead.
        total_tokens += 4

        for key, value in message.items():
            if isinstance(value, str):
                text = value
            else:
                text = json.dumps(value, ensure_ascii=False)

            total_tokens += len(encoding.encode(text))

    # Approximate assistant response prefix.
    total_tokens += 3

    return total_tokens
