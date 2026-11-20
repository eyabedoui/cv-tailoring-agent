
import pytest

from agent.token_counter import count_message_tokens


def test_count_messages_returns_positive_tokens():
    messages = [
        {"role": "user", "content": "Hello"}
    ]

    result = count_message_tokens(messages, "gpt-4o-mini")

    assert result > 0


def test_longer_message_uses_more_tokens():
    short = [
        {"role": "user", "content": "Hello"}
    ]

    long = [
        {
            "role": "user",
            "content": "Hello " * 100,
        }
    ]

    assert (
        count_message_tokens(long, "gpt-4o-mini")
        > count_message_tokens(short, "gpt-4o-mini")
    )


def test_unknown_model_rejected():
    with pytest.raises(ValueError, match="Unknown tokenizer"):
        count_message_tokens(
            [{"role": "user", "content": "Hello"}],
            "completely-unknown-model-xyz",
        )


def test_empty_messages():
    assert count_message_tokens([], "gpt-4o-mini") >= 0
