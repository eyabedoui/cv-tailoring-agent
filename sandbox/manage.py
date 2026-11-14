"""
Sandbox management commands.

    python -m sandbox setup   – create sandbox directory structure
    python -m sandbox seed    – populate sandbox/postings/ with 25 postings
    python -m sandbox reset   – delete state and output files (keep postings)
    python -m sandbox run     – run the agent against job_001 with fake model

Calling seed() implies setup().
"""

import shutil
import subprocess
import sys
from pathlib import Path

_BASE = Path(__file__).parent


def setup() -> None:
    """Create sandbox directory structure if it does not already exist."""
    for sub in ("postings", "output", "state"):
        (_BASE / sub).mkdir(parents=True, exist_ok=True)
    print(f"Sandbox directories created under {_BASE}")


def seed() -> None:
    """Seed sandbox/postings/ with 25 deterministic fictional job postings."""
    setup()
    from sandbox.seed import seed as _seed
    _seed(postings_dir=_BASE / "postings")


def reset() -> None:
    """
    Clear sandbox/output/ and sandbox/state/ contents.

    Deletes the files inside those directories (not the directories themselves)
    so the sandbox is ready for a fresh agent run.  Keeps sandbox/postings/
    and the static markdown files.
    """
    for sub in ("output", "state"):
        target = _BASE / sub
        target.mkdir(parents=True, exist_ok=True)
        for item in target.iterdir():
            if item.is_file():
                item.unlink(missing_ok=True)
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
    print("Sandbox output and state cleared.")


def run(job_url: str = "mock://jobs/job_001") -> None:
    """Run the agent with the fake model and auto-approval."""
    cmd = [
        sys.executable, "-m", "agent",
        "--model", "fake",
        "--auto-approve",
        "--job-url", job_url,
    ]
    subprocess.run(cmd, check=True)
