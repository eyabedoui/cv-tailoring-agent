
"""
Entry point: python -m agent

Extends cli.py's argument parser additively with --job-url, --request, and --model.
"""

import os
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
            "cv_path": "sandbox/output/cv_job_001.md",
            "cover_letter_path": "sandbox/output/cover_letter_job_001.md",
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


def _load_dotenv():
    """Read KEY=VALUE pairs from .env in cwd and set missing env vars.

    Ignores blank lines and lines starting with '#'.  Strips surrounding
    quotes from values.  Never overrides an already-set variable.
    Never prints values.
    """
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Strip surrounding single or double quotes.
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key:
                os.environ.setdefault(key, value)


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
        "--request",
        type=str,
        default=None,
        metavar="TEXT",
        help="Override the generated task message (--job-url is then ignored).",
    )

    parser.add_argument(
        "--model",
        choices=["anthropic", "fake"],
        default="anthropic",
        help="Model backend to use (default: anthropic).",
    )

    return parser


def main(argv=None):
    _load_dotenv()

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

    # Build the initial user message.
    if args.request:
        user_message = args.request
    else:
        user_message = (
            f"Tailor my CV for the job posting at {args.job_url}. "
            "Read the posting and my master CV, match skills, "
            "save a tailored CV and a cover letter, "
            "then submit the application (a human will approve it)."
        )

    checkpoint = create_checkpoint_from_args(args)
    logger = AgentLogger()

    agent = AgentLoop(model=model, logger=logger, checkpoint=checkpoint)
    result = agent.run(initial_messages=[{"role": "user", "content": user_message}])

    print("\n--- Agent finished ---")
    print(f"Answer     : {result['answer']}")
    print(f"Stop reason: {result['stop_reason']}")
    print(f"Steps      : {result['step_count']}")
    print(f"Log file   : {logger.log_file}")

    return result


if __name__ == "__main__":
    main()
