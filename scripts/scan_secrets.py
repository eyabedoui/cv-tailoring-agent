#!/usr/bin/env python3
"""
Scan git-tracked files for accidentally committed API keys.

Patterns flagged:
  - OpenAI-style key:    sk- followed by 20+ alphanumeric/dash/underscore chars
  - Firecrawl-style key: fc- followed by 20+ alphanumeric/dash/underscore chars
  - Non-empty dotenv:    OPENAI_API_KEY or FIRECRAWL_API_KEY assigned a value
    (a bare '=' with nothing after it is clean and is NOT flagged)

Per-line opt-out: append  # scan:ignore  to any line to suppress that hit.

Excluded files (never scanned):
  scripts/scan_secrets.py   (this file — the pattern strings would self-match)
  tests/test_scan_secrets.py

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

# Files whose content is expected to contain key-shaped patterns (never scanned).
_EXCLUDED_PATHS = frozenset({
    "scripts/scan_secrets.py",
    "tests/test_scan_secrets.py",
})


def scan_files(
    paths: list[str | Path],
    excluded_paths: frozenset[str] = _EXCLUDED_PATHS,
) -> list[tuple[str, int, str]]:
    """
    Scan *paths* for API-key patterns.

    Returns a list of (file_path, line_number, redacted_match) tuples.
    Skips binary files, excluded paths, and lines marked with # scan:ignore.
    """
    hits: list[tuple[str, int, str]] = []
    for p in paths:
        p = Path(p)
        if p.suffix.lower() in _BINARY_EXTENSIONS:
            continue
        # Normalize to forward slashes so exclusions work on Windows too.
        rel = str(p).replace("\\", "/")
        if any(rel.endswith(ex) for ex in excluded_paths):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if "# scan:ignore" in line:
                continue
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
