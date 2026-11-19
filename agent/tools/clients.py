"""
PostingClient protocol and default client implementations.

WEB_MODE controls which client is used by read_job_posting:
  fake   – FakePostingClient reads from sandbox/postings/ (offline, default)
  replay – FakePostingClient reads from sandbox/snapshots/ for real-site URLs (W7)
  live   – FirecrawlPostingClient (W4; not yet implemented)

Real clients (Firecrawl, Browser Use) are created ONLY in this file and are
never constructed in tests.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from urllib.parse import urlparse

from agent.errors import make_error, NOT_FOUND
from sandbox.faults import check_fault
from sandbox.portal import Portal


@runtime_checkable
class PostingClient(Protocol):
    """Protocol for all posting fetch clients."""

    def fetch(self, url: str) -> dict:
        """
        Fetch a job posting from the given URL.

        Returns one of:
          {"markdown": str, "url": str, ...}  — success (extra keys allowed for internal use)
          {"error": str, "message": str, ...}  — error dict
        """
        ...


def _extract_own_job_id(url: str) -> str | None:
    """Extract the job_id from an own-site /jobs/<job_id> URL, or None."""
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "jobs":
        return parts[1]
    return None


def _posting_to_markdown(posting: dict) -> str:
    """Serialise a sandbox posting dict to simple markdown for the protocol contract."""
    lines = [
        f"# {posting.get('title', 'Unknown Title')}",
        f"**Company:** {posting.get('company', 'Unknown')}",
        "",
        "## Requirements",
    ]
    for req in posting.get("requirements", []):
        lines.append(f"- {req}")
    lines += ["", "## Description", posting.get("text", "")]
    return "\n".join(lines)


class FakePostingClient:
    """
    Offline posting client backed by sandbox/postings/.

    For own-site URLs (http://host/jobs/<job_id>), reads the posting JSON
    from the sandbox and returns it alongside the markdown representation.
    For all other URLs, returns NOT_FOUND (snapshot support added in W7).
    """

    def __init__(self, sandbox_dir: str | None = None):
        self._portal = Portal(sandbox_dir=sandbox_dir)

    def fetch(self, url: str) -> dict:
        fault = check_fault("read", self._portal.state_dir)
        if fault is not None:
            return fault

        job_id = _extract_own_job_id(url)
        if job_id is None:
            return make_error(NOT_FOUND, f"Cannot resolve job posting from URL {url!r}")

        posting = self._portal.get_posting(job_id)
        if posting is None:
            return make_error(NOT_FOUND, f"Job posting {job_id!r} was not found in the sandbox")

        return {
            "markdown": _posting_to_markdown(posting),
            "url": url,
            "_posting": posting,
        }
