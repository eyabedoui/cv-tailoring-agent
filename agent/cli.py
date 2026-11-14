
"""
Command-line configuration for the CV-tailoring agent.

Supports:
- Interactive human approval (default)
- --auto-approve
- --auto-reject
- --scripted-decisions yes,no,...
"""

import argparse

from agent.checkpoint import HumanApprovalCheckpoint


def create_argument_parser():
    """Create the command-line argument parser."""

    parser = argparse.ArgumentParser(
        description="CV-tailoring agent execution options."
    )

    approval_group = parser.add_mutually_exclusive_group()

    approval_group.add_argument(
        "--auto-approve",
        action="store_true",
        help="Automatically approve application submissions.",
    )

    approval_group.add_argument(
        "--auto-reject",
        action="store_true",
        help="Automatically reject application submissions.",
    )

    parser.add_argument(
        "--scripted-decisions",
        type=str,
        default=None,
        metavar="DECISIONS",
        help=(
            "Comma-separated approval decisions for testing, "
            "for example: yes,no,yes."
        ),
    )

    return parser


def parse_cli_args(argv=None):
    """Parse command-line arguments."""

    parser = create_argument_parser()
    args = parser.parse_args(argv)

    if args.scripted_decisions is not None:
        if args.auto_approve or args.auto_reject:
            parser.error(
                "--scripted-decisions cannot be combined with "
                "--auto-approve or --auto-reject."
            )

        values = [
            value.strip().lower()
            for value in args.scripted_decisions.split(",")
        ]

        if not values or any(
            value not in ("yes", "y", "no", "n")
            for value in values
        ):
            parser.error(
                "Scripted decisions must contain only yes or no."
            )

        args.scripted_decisions = [
            value in ("yes", "y")
            for value in values
        ]

    return args


def create_checkpoint_from_args(args):
    """Create a human checkpoint using parsed CLI options."""

    return HumanApprovalCheckpoint(
        auto_approve=args.auto_approve,
        auto_reject=args.auto_reject,
        scripted_decisions=args.scripted_decisions,
    )


def run_agent_with_cli(model, argv=None, logger=None):
    """
    Configure and run the agent using command-line approval options.

    The model must implement call_model(messages, tools).
    """

    from agent.loop import AgentLoop

    args = parse_cli_args(argv)

    checkpoint = create_checkpoint_from_args(args)

    agent = AgentLoop(
        model=model,
        logger=logger,
        checkpoint=checkpoint,
    )

    return agent.run()
