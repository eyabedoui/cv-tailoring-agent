
"""
API cost calculation utilities for the CV-tailoring agent.

All prices are expressed in USD per million tokens.
"""


def calculate_token_cost(
    input_tokens: int,
    output_tokens: int,
    input_price_per_mtok: float,
    output_price_per_mtok: float,
) -> float:
    """Calculate the estimated USD cost of token usage."""

    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts cannot be negative.")

    if input_price_per_mtok < 0 or output_price_per_mtok < 0:
        raise ValueError("Token prices cannot be negative.")

    return (
        input_tokens * input_price_per_mtok
        + output_tokens * output_price_per_mtok
    ) / 1_000_000

def estimate_request_cost(
    messages: list[dict],
    model: str,
    max_output_tokens: int,
    input_price_per_mtok: float,
    output_price_per_mtok: float,
) -> float:
    """
    Estimate the USD cost of an OpenAI request before execution.

    This is a planning estimate, not a guaranteed upper bound.
    """
    from agent.token_counter import count_message_tokens

    if max_output_tokens <= 0:
        raise ValueError("Maximum output tokens must be positive.")

    input_tokens = count_message_tokens(messages, model)

    return calculate_token_cost(
        input_tokens=input_tokens,
        output_tokens=max_output_tokens,
        input_price_per_mtok=input_price_per_mtok,
        output_price_per_mtok=output_price_per_mtok,
    )
