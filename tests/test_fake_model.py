
import pytest

from agent.fake_model import FakeModel


def test_fake_model_returns_scripted_responses_in_order():
    responses = [
        {
            "type": "tool_call",
            "tool_name": "read_job_posting",
            "arguments": {"url": "http://127.0.0.1:5000/jobs/job_001"},
            "tokens_in": 0,
            "tokens_out": 0,
        },
        {
            "type": "final",
            "content": "Process complete.",
            "tokens_in": 0,
            "tokens_out": 0,
        },
    ]

    model = FakeModel(responses)

    first = model.call_model([], [])
    second = model.call_model([], [])

    assert first["tool_name"] == "read_job_posting"
    assert second["type"] == "final"
    assert model.call_count == 2


def test_fake_model_raises_when_responses_are_exhausted():
    model = FakeModel([
        {"type": "final", "content": "Done."}
    ])

    model.call_model([], [])

    with pytest.raises(RuntimeError):
        model.call_model([], [])


def test_fake_model_does_not_modify_original_responses():
    responses = [
        {"type": "final", "content": "Done."}
    ]

    model = FakeModel(responses)
    model.call_model([], [])

    assert responses[0]["content"] == "Done."
