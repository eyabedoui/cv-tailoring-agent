#!/usr/bin/env python3
"""
Scan git-tracked files for accidentally committed API keys.

Patterns flagged:
  - sk-[A-Za-z0-9_-]{20,}          OpenAI-style secret key
  - fc-[A-Za-z0-9_-]{20,}          Firecrawl-style secret key
  - OPENAI_API_KEY=<non-empty>      dotenv assignment with a value
  - FIRECRAWL_API_KEY=<non-empty>   dotenv assignment with a value

Usage:
  python scripts/scan_secrets.py

Exit code 0 = clean, 1 = secrets found, 2 = error (not in a git repo).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_KEY_PATTERNS = re.compile(
    r"sk-[A-Za-z0-9_\-]{20,}"
    r"|fc-[A-Za-z0-9_\-]{20,}"
    r"|OPENAI_API_KEY\s*=\s*\S+"
    r"|FIRECRAWL_API_KEY\s*=\s*\S+",
)

_BINARY_EXTENSIONS = frozenset(
    ".png .jpg .jpeg .gif .ico .pdf .pyc .pyo .zip .tar .gz .whl .bin .db .sqlite".split()
)


def scan_files(paths: list[str | Path]) -> list[tuple[str, int, str]]:
    """
    Scan *paths* for API-key patterns.

    Returns a list of (file_path, line_number, redacted_match) tuples.
    Does not read binary files (filtered by extension).
    """
    hits: list[tuple[str, int, str]] = []
    for p in paths:
        p = Path(p)
        if p.suffix.lower() in _BINARY_EXTENSIONS:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            m = _KEY_PATTERNS.search(line)
            if m:
                matched = m.group()
                redacted = matched[:6] + "***"
                hits.append((str(p), lineno, redacted))
    return hits


def _git_tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print("Error: 'git ls-files' failed — run this script from inside the repository root.")
        sys.exit(2)
    return [Path(p) for p in result.stdout.splitlines() if p.strip()]


def main() -> None:
    paths = _git_tracked_files()
    hits = scan_files(paths)

    if hits:
        for path, lineno, redacted in hits:
            print(f"FOUND: {path}:{lineno}: {redacted}")
        print(f"\n{len(hits)} secret(s) found in {len(paths)} tracked file(s). Fix before committing.")
        sys.exit(1)
    else:
        print(f"OK: scanned {len(paths)} tracked file(s) — no secrets found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
