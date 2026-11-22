
"""
Entry point: python -m agent

Supports three model backends:
- fake: Offline scripted testing
- openai: OpenAI API
- groq: Groq API

Preserves human approval, budget tracking, and agent stop rules.
"""

import os
import sys

from agent.cli import (
    create_argument_parser,
    create_checkpoint_from_args,
)
from agent.fake_model import FakeModel
from agent.logger import AgentLogger
from agent.loop import AgentLoop
from agent.model import ModelUnavailableError
from agent.sites import own_job_url
from agent.budget import BudgetTracker


FAKE_WALKTHROUGH_RESPONSES = [
    {
        "type": "tool_call",
        "tool_name": "read_job_posting",
        "arguments": {"url": own_job_url("job_001")},
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
            "job": {
                "title": "Junior AI Engineer",
                "requirements": ["Python"],
            },
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
            "cv_path": "cv_job_001.md",
            "cover_letter_path": "cover_letter_job_001.md",
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


SEARCH_THEN_TAILOR_RESPONSES = [
    {
        "type": "tool_call",
        "tool_name": "find_jobs",
        "arguments": {
            "query": "python engineer",
            "site": "tanitjobs",
        },
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    {
        "type": "tool_call",
        "tool_name": "read_job_posting",
        "arguments": {"url": own_job_url("job_001")},
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
            "job": {
                "title": "Junior AI Engineer",
                "requirements": ["Python"],
            },
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
            "text": (
                "Dear Hiring Manager, I am excited to apply "
                "after finding the posting via search."
            ),
            "job_id": "job_001",
            "kind": "cover_letter",
        },
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    {
        "type": "tool_call",
        "tool_name": "submit_application",
        "arguments": {
            "cv_path": "cv_job_001.md",
            "cover_letter_path": "cover_letter_job_001.md",
            "job_id": "job_001",
        },
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    {
        "type": "final",
        "content": (
            "Found the job via search, tailored the CV and cover letter, "
            "and submitted the application for Junior AI Engineer."
        ),
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
]


def _load_dotenv():
    """Load missing environment variables from the local .env file."""
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

            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in ('"', "'")
            ):
                value = value[1:-1]

            if key:
                os.environ.setdefault(key, value)


def _build_parser():
    parser = create_argument_parser()

    parser.add_argument(
        "--job-url",
        type=str,
        default=own_job_url("job_001"),
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
        choices=["openai", "groq", "fake"],
        default="openai",
        help="Model backend (default: openai).",
    )

    return parser


def main(argv=None):
    _load_dotenv()

    parser = _build_parser()
    args = parser.parse_args(argv)

    # Validate scripted human-approval decisions.
    if args.scripted_decisions is not None:
        if args.auto_approve or args.auto_reject:
            parser.error(
                "--scripted-decisions cannot be combined with "
                "--auto-approve or --auto-reject."
            )

        values = [
            v.strip().lower()
            for v in args.scripted_decisions.split(",")
        ]

        if not values or any(
            v not in ("yes", "y", "no", "n")
            for v in values
        ):
            parser.error(
                "Scripted decisions must contain only yes or no."
            )

        args.scripted_decisions = [
            v in ("yes", "y")
            for v in values
        ]

    # Select the model backend.
    if args.model == "fake":
        model = FakeModel(FAKE_WALKTHROUGH_RESPONSES)

    elif args.model == "groq":
        from agent.groq_model import GroqModel

        budget_limit = float(
            os.environ.get("GROQ_API_BUDGET_USD", "0")
        )

        budget = BudgetTracker(limit_usd=budget_limit)

        model = GroqModel(budget=budget)

    else:
        from agent.model import OpenAIModel

        budget_limit = float(
            os.environ.get("API_BUDGET_USD", "0")
        )

        budget = BudgetTracker(limit_usd=budget_limit)

        model = OpenAIModel(budget=budget)

    # Build the initial user request.
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

    agent = AgentLoop(
        model=model,
        logger=logger,
        checkpoint=checkpoint,
    )

    try:
        result = agent.run(
            initial_messages=[
                {
                    "role": "user",
                    "content": user_message,
                }
            ]
        )

    except ModelUnavailableError as exc:
        print(f"Model unavailable: {exc}")
        sys.exit(2)

    print("\n--- Agent finished ---")
    print(f"Answer     : {result['answer']}")
    print(f"Stop reason: {result['stop_reason']}")
    print(f"Steps      : {result['step_count']}")
    print(f"Log file   : {logger.log_file}")

    return result


if __name__ == "__main__":
    main()
