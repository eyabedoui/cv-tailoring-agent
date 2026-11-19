"""
find_jobs tool and search client implementations.

WEB_MODE env var selects the client:
  "fake" or "replay" (default) → FakeSearchClient (deterministic, offline)
  "live"                       → BrowserSearchClient (browser-use + OpenAI)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from agent.config import SANDBOX_DIR
from agent.errors import (
    INVALID_ARGUMENTS,
    PORTAL_DOWN,
    SITE_BLOCKED,
    SITE_NOT_ALLOWED,
    make_error,
)
from agent.sites import site_names, url_belongs_to_site


# ---------------------------------------------------------------------------
# SearchClient protocol
# ---------------------------------------------------------------------------

class SearchClient(Protocol):
    def search(self, query: str, site: str) -> list[dict]:
        """Return a list of raw job-result dicts for the given query and site."""


# ---------------------------------------------------------------------------
# FakeSearchClient
# ---------------------------------------------------------------------------

class FakeSearchClient:
    """
    Deterministic search client for tests and offline runs.

    Results are built from sandbox/seed.py POSTINGS re-labelled to look like
    the requested site.  Same query always produces the same ordered results.

    Keyword matching: case-insensitive overlap of any query keyword with
    title, snippet, or company.  Falls back to the first N postings when no
    keyword matches.
    """

    def search(self, query: str, site: str) -> list[dict]:
        from sandbox.seed import POSTINGS
        from agent.sites import host_for

        host = host_for(site)
        q_words = set(query.lower().split())

        matched: list[dict] = []
        unmatched: list[dict] = []

        for posting in POSTINGS:
            combined = (
                posting["title"].lower()
                + " "
                + posting["text"].lower()
                + " "
                + posting["company"].lower()
            )
            if any(word in combined for word in q_words):
                matched.append(posting)
            else:
                unmatched.append(posting)

        source = matched if matched else POSTINGS

        results = []
        for p in source:
            results.append({
                "job_id": p["job_id"],
                "title": p["title"],
                "company": p["company"],
                "location": "Tunisia",
                "url": f"https://{host}/jobs/{p['job_id']}",
                "site": site,
                "snippet": p["text"][:240],
            })

        return results


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def _get_search_client() -> SearchClient:
    mode = os.environ.get("WEB_MODE", "fake").lower().strip()
    if mode == "live":
        from agent.tools.clients import BrowserSearchClient
        return BrowserSearchClient()
    return FakeSearchClient()


# ---------------------------------------------------------------------------
# find_jobs tool function
# ---------------------------------------------------------------------------

def find_jobs(query: str, site: str, _client: SearchClient | None = None) -> dict:
    """
    Search for jobs matching *query* on *site*.

    Returns:
        {"jobs": [...], "site": site, "count": n, "truncated": bool}
    or an error dict.

    Validation:
      - site must be in the enabled allowlist (SITE_NOT_ALLOWED if not).
      - query validated by pydantic schema (non-empty, max 200 chars).
    Defence:
      - Drops any result whose URL does not belong to the requested site.
      - Truncates at 10 results.
      - Field lengths: title 120, company 80, snippet 240.
    """
    # --- fault injection (blocked mode fires here) ---
    from sandbox.faults import check_fault
    state_dir = Path(SANDBOX_DIR) / "state"
    fault = check_fault("search", state_dir)
    if fault is not None:
        return fault

    # --- site allowlist check ---
    allowed = site_names()
    if site not in allowed:
        return make_error(
            SITE_NOT_ALLOWED,
            f"Site {site!r} is not allowed. Allowed sites: {', '.join(sorted(allowed))}.",
        )

    # --- throttle + execute search (live mode only) ---
    mode = os.environ.get("WEB_MODE", "fake").lower().strip()
    if mode == "live" and _client is None:
        from agent.tools.throttle import throttle
        from agent.sites import host_for
        throttle(host_for(site))

    client = _client or _get_search_client()
    try:
        raw_results = client.search(query, site)
    except Exception as exc:
        return make_error(PORTAL_DOWN, f"Search failed: {exc}")

    # --- filter foreign-host results (defence in depth) ---
    safe_results: list[dict] = []
    for item in raw_results:
        url = item.get("url", "")
        if not url_belongs_to_site(url, site):
            continue
        safe_results.append(item)

    # --- truncate + field length limits ---
    truncated = len(safe_results) > 10
    safe_results = safe_results[:10]

    jobs = []
    for item in safe_results:
        jobs.append({
            "job_id":  str(item.get("job_id", "")),
            "title":   str(item.get("title",   ""))[:120],
            "company": str(item.get("company", ""))[:80],
            "location":str(item.get("location","")) ,
            "url":     str(item.get("url",     "")),
            "site":    site,
            "snippet": str(item.get("snippet", ""))[:240],
        })

    # --- usage log (live mode only) ---
    if mode == "live" and _client is None:
        from agent.tools.usage_log import log_usage
        from agent.sites import host_for
        log_usage("find_jobs", host_for(site), "success")

    return {
        "jobs": jobs,
        "site": site,
        "count": len(jobs),
        "truncated": truncated,
    }
