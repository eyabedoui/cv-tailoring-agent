
"""
Entry point: python -m agent

Extends cli.py's argument parser additively with --job-url and --model.
"""

import sys

from agent.cli import create_argument_parser, create_checkpoint_from_args
from agent.fake_model import FakeModel
from agent.logger import AgentLogger
from agent.loop import AgentLoop
from agent.config import ALLOWED_URL_PREFIX


FAKE_WALKTHROUGH_RESPONSES = [
    {
        "type": "tool_call",
        "tool_name": "read_job_posting",
        "arguments": {"url": "mock://jobs/job_001"},
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    {
        "type": "tool_call",
        "tool_name": "read_master_cv",
        "arguments": {},
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    {
        "type": "tool_call",
        "tool_name": "match_skills",
        "arguments": {
            "cv_text": "Python, SQL",
            "job": {"title": "Junior AI Engineer", "requirements": ["Python"]},
        },
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    {
        "type": "tool_call",
        "tool_name": "save_tailored_cv",
        "arguments": {
            "text": "Tailored CV for Junior AI Engineer",
            "job_id": "job_001",
            "kind": "cv",
        },
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    {
        "type": "tool_call",
        "tool_name": "save_tailored_cv",
        "arguments": {
            "text": "Dear Hiring Manager, I am excited to apply.",
            "job_id": "job_001",
            "kind": "cover_letter",
        },
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    {
        "type": "tool_call",
        "tool_name": "submit_application",
        "arguments": {
            "cv_path": "sandbox/output/job_001_cv.txt",
            "cover_letter_path": "sandbox/output/job_001_cover_letter.txt",
            "job_id": "job_001",
        },
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    {
        "type": "final",
        "content": (
            "The application for Junior AI Engineer at Example Company "
            "has been tailored and submitted successfully."
        ),
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
]


def _build_parser():
    parser = create_argument_parser()

    parser.add_argument(
        "--job-url",
        type=str,
        default=f"{ALLOWED_URL_PREFIX}jobs/job_001",
        metavar="URL",
        help="URL of the job posting to process.",
    )

    parser.add_argument(
        "--model",
        choices=["anthropic", "fake"],
        default="anthropic",
        help="Model backend to use (default: anthropic).",
    )

    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Validate scripted_decisions the same way cli.py does.
    if args.scripted_decisions is not None:
        if args.auto_approve or args.auto_reject:
            parser.error(
                "--scripted-decisions cannot be combined with "
                "--auto-approve or --auto-reject."
            )
        values = [v.strip().lower() for v in args.scripted_decisions.split(",")]
        if not values or any(v not in ("yes", "y", "no", "n") for v in values):
            parser.error("Scripted decisions must contain only yes or no.")
        args.scripted_decisions = [v in ("yes", "y") for v in values]

    if args.model == "fake":
        model = FakeModel(FAKE_WALKTHROUGH_RESPONSES)
    else:
        from agent.model import AnthropicModel
        model = AnthropicModel()

    checkpoint = create_checkpoint_from_args(args)
    logger = AgentLogger()

    agent = AgentLoop(model=model, logger=logger, checkpoint=checkpoint)
    result = agent.run()

    print("\n--- Agent finished ---")
    print(f"Answer     : {result['answer']}")
    print(f"Stop reason: {result['stop_reason']}")
    print(f"Steps      : {result['step_count']}")
    print(f"Log file   : {logger.log_file}")

    return result


if __name__ == "__main__":
    main()
