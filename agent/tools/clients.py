"""
PostingClient / SearchClient real and fake implementations.

WEB_MODE controls which client is used:
  fake   – FakePostingClient / FakeSearchClient (offline, default)
  replay – FakePostingClient reads from sandbox/snapshots/ for real-site URLs (W7)
  live   – FirecrawlPostingClient (W4) / BrowserSearchClient (W3)

Real clients (Firecrawl, Browser Use, OpenAI) are created ONLY in this file and
are never constructed in tests.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse

from agent.errors import make_error, NOT_FOUND, PORTAL_DOWN
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
        if job_id is not None:
            posting = self._portal.get_posting(job_id)
            if posting is None:
                return make_error(NOT_FOUND, f"Job posting {job_id!r} was not found in the sandbox")
            return {
                "markdown": _posting_to_markdown(posting),
                "url": url,
                "_posting": posting,
            }

        # Non-own-site URL: check snapshots/ in replay mode.
        mode = os.environ.get("WEB_MODE", "fake").lower().strip()
        if mode == "replay":
            return self._fetch_snapshot(url)

        return make_error(NOT_FOUND, f"Cannot resolve job posting from URL {url!r}")

    def _fetch_snapshot(self, url: str) -> dict:
        """Load a previously saved snapshot for *url* from sandbox/snapshots/."""
        from agent.sites import url_belongs_to_site, site_names

        h = hashlib.sha256(url.encode()).hexdigest()[:8]
        site = "ext"
        for s in site_names():
            if url_belongs_to_site(url, s):
                site = s
                break
        job_id = f"{site}-{h}"

        snapshots_dir = self._portal.postings_dir.parent / "snapshots"
        snapshot_path = snapshots_dir / f"{job_id}.json"
        if not snapshot_path.exists():
            return make_error(NOT_FOUND, f"No snapshot found for URL {url!r} (expected {snapshot_path})")

        with open(snapshot_path, encoding="utf-8") as fh:
            data = json.load(fh)

        return {"markdown": data.get("markdown", ""), "url": url}


class FirecrawlPostingClient:
    """
    Real posting client using Firecrawl (V1FirecrawlApp) to scrape job pages.

    Env vars:
      FIRECRAWL_API_KEY – required for live runs

    Error mapping:
      404 / no content          → NOT_FOUND
      401 / 403 / login/captcha → SITE_BLOCKED
      429 / 5xx / connection    → PORTAL_DOWN (retryable)
      timeout                   → TIMEOUT (retryable)
      empty markdown            → EMPTY_POSTING
    """

    def fetch(self, url: str) -> dict:
        import os
        from pathlib import Path
        from agent.config import SANDBOX_DIR
        from firecrawl import V1FirecrawlApp
        from agent.errors import PORTAL_DOWN as _PORTAL_DOWN, SITE_BLOCKED as _SITE_BLOCKED, TIMEOUT as _TIMEOUT, EMPTY_POSTING as _EMPTY_POSTING

        fault = check_fault("read", Path(SANDBOX_DIR) / "state")
        if fault is not None:
            return fault

        api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        app = V1FirecrawlApp(api_key=api_key)
        try:
            response = app.scrape_url(url, formats=["markdown"])
        except Exception as exc:
            return _map_firecrawl_error(exc, url)

        markdown = response.markdown if response.markdown else ""
        if not markdown.strip():
            return make_error(_EMPTY_POSTING, f"No content scraped from {url!r}")

        return {"markdown": markdown, "url": url}


def _map_firecrawl_error(exc: Exception, url: str) -> dict:
    """Map a firecrawl exception to the agent error contract."""
    from agent.errors import NOT_FOUND, PORTAL_DOWN, SITE_BLOCKED, TIMEOUT, EMPTY_POSTING
    try:
        from firecrawl.v2.utils.error_handler import (
            RateLimitError, InternalServerError, UnauthorizedError,
            RequestTimeoutError, DNSResolutionError, TLSError,
            WebsiteNotSupportedError, ProviderTermsRequiredError, BadRequestError,
        )
        if isinstance(exc, RequestTimeoutError):
            return make_error(TIMEOUT, f"Firecrawl timed out scraping {url!r}: {exc}", retryable=True)
        if isinstance(exc, (UnauthorizedError, WebsiteNotSupportedError, ProviderTermsRequiredError)):
            return make_error(SITE_BLOCKED, f"Site blocked or requires login for {url!r}: {exc}", retryable=False)
        if isinstance(exc, (RateLimitError, InternalServerError)):
            return make_error(PORTAL_DOWN, f"Firecrawl error for {url!r}: {exc}", retryable=True)
        if isinstance(exc, (DNSResolutionError, TLSError)):
            return make_error(PORTAL_DOWN, f"Connection error for {url!r}: {exc}", retryable=True)
        if isinstance(exc, BadRequestError):
            # Check for 404-like message
            msg = str(exc).lower()
            if "404" in msg or "not found" in msg:
                return make_error(NOT_FOUND, f"Page not found: {url!r}", retryable=False)
            return make_error(PORTAL_DOWN, f"Bad request for {url!r}: {exc}", retryable=False)
    except ImportError:
        pass
    # Fallback: check HTTP status code if available
    status = getattr(exc, "status_code", None)
    if status == 404:
        return make_error(NOT_FOUND, f"Page not found (404): {url!r}", retryable=False)
    if status in (401, 403):
        return make_error(SITE_BLOCKED, f"Access denied ({status}): {url!r}", retryable=False)
    if status == 429 or (status and status >= 500):
        return make_error(PORTAL_DOWN, f"Server error ({status}): {url!r}", retryable=True)
    return make_error(PORTAL_DOWN, f"Firecrawl scrape failed for {url!r}: {exc}", retryable=True)


class BrowserSearchClient:
    """
    Real job-search client using browser-use + OpenAI.

    Env vars:
      OPENAI_API_KEY     – required for live runs
      SEARCH_LLM_MODEL   – model name (default: gpt-4o-mini)
    """

    def search(self, query: str, site: str) -> list[dict]:
        import asyncio
        import os
        from pydantic import BaseModel
        from browser_use import Agent
        from browser_use.llm import ChatOpenAI
        from agent.sites import host_for

        api_key = os.environ.get("OPENAI_API_KEY", "")
        model = os.environ.get("SEARCH_LLM_MODEL", "gpt-4o-mini")
        host = host_for(site)

        class _JobResult(BaseModel):
            job_id: str = ""
            title: str = ""
            company: str = ""
            location: str = ""
            url: str = ""
            snippet: str = ""

        class _SearchOutput(BaseModel):
            jobs: list[_JobResult] = []

        task = (
            f"Go to https://{host}. Search for job postings matching the query: '{query}'. "
            f"Collect up to 10 listings with title, company, location, URL, and a short snippet. "
            f"Return as structured data."
        )

        llm = ChatOpenAI(model=model, api_key=api_key)
        agent = Agent(task=task, llm=llm, output_model_schema=_SearchOutput)
        history = asyncio.run(agent.run(max_steps=20, timeout=120))
        output = history.structured_output
        if output is None:
            return []
        return [
            {
                "job_id": job.job_id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "site": site,
                "snippet": job.snippet,
            }
            for job in output.jobs
        ]


class BrowserSubmitClient:
    """
    Submit an application by navigating to the apply page and clicking the button.

    Env vars:
      OPENAI_API_KEY    – required for live runs
      SUBMIT_LLM_MODEL  – model name (default: gpt-4o-mini)
    """

    def submit(self, job_id: str, apply_url: str) -> dict:
        import asyncio
        import os
        from pydantic import BaseModel
        from browser_use import Agent
        from browser_use.llm import ChatOpenAI

        api_key = os.environ.get("OPENAI_API_KEY", "")
        model = os.environ.get("SUBMIT_LLM_MODEL", "gpt-4o-mini")

        class _SubmitResult(BaseModel):
            status: str = ""
            application_id: str = ""

        task = (
            f"Go to {apply_url}. "
            f"Find the button with id 'submit-application' and click it. "
            f"Wait for the JSON confirmation response. "
            f"Extract the status and application_id from the response."
        )

        llm = ChatOpenAI(model=model, api_key=api_key)
        agent = Agent(task=task, llm=llm, output_model_schema=_SubmitResult)
        history = asyncio.run(agent.run(max_steps=10, timeout=60))
        output = history.structured_output

        if output is None or output.status != "submitted":
            return make_error(PORTAL_DOWN, f"Browser submit to {apply_url!r} did not confirm submission")

        return {
            "status": "submitted",
            "application_id": output.application_id or f"app_{job_id}",
        }
