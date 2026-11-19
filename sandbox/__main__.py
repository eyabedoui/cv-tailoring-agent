"""
Entry point for  python -m sandbox <command>.

Commands: setup | setup-web | seed | reset | run | serve | export-static | export | snapshot | smoke-web
"""

import argparse
import sys

from sandbox.manage import export, export_static, reset, run, seed, serve, setup, setup_web, snapshot, smoke_web


def main() -> None:
    parser = argparse.ArgumentParser(prog="sandbox", description="Manage the CV-agent sandbox.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Create sandbox dirs and install Playwright Chromium (idempotent).")
    sub.add_parser("setup-web", help="Alias for setup — installs Playwright Chromium.")
    sub.add_parser("seed", help="Populate sandbox/postings/ with 25 job postings.")
    sub.add_parser("reset", help="Clear sandbox output and state (keeps postings).")

    run_p = sub.add_parser("run", help="Run the agent with the fake model.")
    run_p.add_argument(
        "--job-url",
        default=None,
        help="Job posting URL to pass to the agent (default: own site job_001).",
    )

    serve_p = sub.add_parser("serve", help="Start the Flask apply site.")
    serve_p.add_argument(
        "--port", type=int, default=5000, metavar="N",
        help="Port to listen on (default: 5000).",
    )

    es_p = sub.add_parser("export-static",
                          help="Export postings as a static HTML site.")
    es_p.add_argument(
        "--dest", default=None, metavar="PATH",
        help="Destination directory (default: sandbox/site/).",
    )
    es_p.add_argument(
        "--postings-dir", default=None, metavar="PATH",
        help="Postings source directory (default: sandbox/postings/).",
    )

    # Kept as an alias so existing scripts that call 'export' still work.
    exp_p = sub.add_parser("export",
                           help="Alias for export-static.")
    exp_p.add_argument("--dest", default=None, metavar="PATH")

    snap_p = sub.add_parser("snapshot",
                            help="Fetch URL with Firecrawl and save to sandbox/snapshots/.")
    snap_p.add_argument("url", help="Job posting URL to snapshot.")
    snap_p.add_argument(
        "--snapshots-dir", default=None, metavar="PATH",
        help="Snapshots directory (default: sandbox/snapshots/).",
    )
    snap_p.add_argument(
        "--full", action="store_true", default=False,
        help="Store full markdown (default: first 3000 chars only, PII scrubbed).",
    )

    sub.add_parser(
        "smoke-web",
        help="MANUAL integration test — requires OPENAI_API_KEY and FIRECRAWL_API_KEY. Never run from pytest.",
    )

    args = parser.parse_args()

    if args.command == "setup":
        setup()
    elif args.command == "setup-web":
        setup_web()
    elif args.command == "seed":
        seed()
    elif args.command == "reset":
        reset()
    elif args.command == "run":
        from agent.sites import own_job_url
        run(job_url=args.job_url or own_job_url("job_001"))
    elif args.command == "serve":
        serve(port=args.port)
    elif args.command == "export-static":
        export_static(dest=args.dest, postings_dir=args.postings_dir)
    elif args.command == "export":
        export(dest=args.dest)
    elif args.command == "snapshot":
        snapshot(url=args.url, snapshots_dir=args.snapshots_dir, full=args.full)
    elif args.command == "smoke-web":
        smoke_web()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
