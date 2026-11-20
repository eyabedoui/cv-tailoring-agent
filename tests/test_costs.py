
import pytest

from agent.costs import calculate_token_cost


def test_calculate_token_cost():
    cost = calculate_token_cost(
        input_tokens=2000,
        output_tokens=500,
        input_price_per_mtok=1.0,
        output_price_per_mtok=4.0,
    )

    assert cost == pytest.approx(0.004)


def test_zero_tokens_cost_zero():
    assert calculate_token_cost(0, 0, 1.0, 4.0) == 0.0


def test_negative_tokens_rejected():
    with pytest.raises(ValueError):
        calculate_token_cost(-1, 100, 1.0, 4.0)


def test_negative_prices_rejected():
    with pytest.raises(ValueError):
        calculate_token_cost(100, 100, -1.0, 4.0)


def test_zero_prices():
    assert calculate_token_cost(1000, 500, 0.0, 0.0) == 0.0
