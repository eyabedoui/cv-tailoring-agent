
import pytest

from agent.costs import estimate_request_cost


def test_estimate_request_cost_is_positive():
    result = estimate_request_cost(
        messages=[{"role": "user", "content": "Hello"}],
        model="gpt-4o-mini",
        max_output_tokens=100,
        input_price_per_mtok=1.0,
        output_price_per_mtok=4.0,
    )

    assert result > 0


def test_larger_output_limit_costs_more():
    messages = [{"role": "user", "content": "Hello"}]

    small = estimate_request_cost(
        messages, "gpt-4o-mini", 100, 1.0, 4.0
    )

    large = estimate_request_cost(
        messages, "gpt-4o-mini", 1000, 1.0, 4.0
    )

    assert large > small


def test_invalid_output_limit_rejected():
    with pytest.raises(ValueError, match="Maximum output tokens"):
        estimate_request_cost(
            [{"role": "user", "content": "Hello"}],
            "gpt-4o-mini",
            0,
            1.0,
            4.0,
        )


def test_unknown_model_rejected():
    with pytest.raises(ValueError, match="Unknown tokenizer"):
        estimate_request_cost(
            [{"role": "user", "content": "Hello"}],
            "unknown-model-xyz",
            100,
            1.0,
            4.0,
        )
