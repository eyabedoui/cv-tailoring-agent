
import pytest
from agent.cli import run_agent_with_cli
from agent.fake_model import FakeModel
from agent.cli import (
    parse_cli_args,
    create_checkpoint_from_args,
)


def test_cli_auto_approve():
    args = parse_cli_args(["--auto-approve"])

    checkpoint = create_checkpoint_from_args(args)

    assert checkpoint.auto_approve is True
    assert checkpoint.auto_reject is False


def test_cli_auto_reject():
    args = parse_cli_args(["--auto-reject"])

    checkpoint = create_checkpoint_from_args(args)

    assert checkpoint.auto_approve is False
    assert checkpoint.auto_reject is True


def test_cli_default_is_interactive():
    args = parse_cli_args([])

    checkpoint = create_checkpoint_from_args(args)

    assert checkpoint.auto_approve is False
    assert checkpoint.auto_reject is False
    assert checkpoint.scripted_decisions is None


def test_cli_scripted_decisions():
    args = parse_cli_args([
        "--scripted-decisions",
        "yes,no,yes",
    ])

    checkpoint = create_checkpoint_from_args(args)

    assert checkpoint.scripted_decisions == [
        True,
        False,
        True,
    ]


def test_cli_scripted_decisions_accept_short_forms():
    args = parse_cli_args([
        "--scripted-decisions",
        "y,n",
    ])

    assert args.scripted_decisions == [True, False]


def test_cli_rejects_invalid_scripted_decisions():
    with pytest.raises(SystemExit):
        parse_cli_args([
            "--scripted-decisions",
            "yes,maybe",
        ])


def test_cli_rejects_scripted_decisions_with_auto_approve():
    with pytest.raises(SystemExit):
        parse_cli_args([
            "--auto-approve",
            "--scripted-decisions",
            "yes,no",
        ])


def test_cli_rejects_scripted_decisions_with_auto_reject():
    with pytest.raises(SystemExit):
        parse_cli_args([
            "--auto-reject",
            "--scripted-decisions",
            "yes,no",
        ])
def test_run_agent_with_cli_executes_agent():
    model = FakeModel([
        {
            "type": "final",
            "content": "CV tailoring workflow completed.",
        }
    ])

    result = run_agent_with_cli(
        model=model,
        argv=["--auto-approve"],
    )

    assert result["answer"] == "CV tailoring workflow completed."
    assert result["stop_reason"] == "done"
    assert model.call_count == 1