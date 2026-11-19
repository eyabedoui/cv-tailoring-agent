"""
Entry point for  python -m sandbox <command>.

Commands: setup | seed | reset | run [--job-url URL]
"""

import argparse
import sys

from sandbox.manage import reset, run, seed, setup


def main() -> None:
    parser = argparse.ArgumentParser(prog="sandbox", description="Manage the CV-agent sandbox.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Create sandbox directory structure.")
    sub.add_parser("seed", help="Populate sandbox/postings/ with 25 job postings.")
    sub.add_parser("reset", help="Clear sandbox output and state (keeps postings).")
    run_p = sub.add_parser("run", help="Run the agent with the fake model.")
    run_p.add_argument(
        "--job-url",
        default=None,
        help="Job posting URL to pass to the agent (default: own site job_001).",
    )

    args = parser.parse_args()

    if args.command == "setup":
        setup()
    elif args.command == "seed":
        seed()
    elif args.command == "reset":
        reset()
    elif args.command == "run":
        from agent.sites import own_job_url
        run(job_url=args.job_url or own_job_url("job_001"))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
