"""
Site allowlist for the CV-tailoring agent.

Allowed sites are defined in agent/allowed_sites.json (committed, no secrets).
The path can be overridden by the CV_AGENT_ALLOWED_SITES env var for tests.

Security rules enforced by is_url_allowed():
  - https:// only (http:// rejected)
  - No userinfo (e.g. https://evil@trusted.com is rejected)
  - Exact host match OR subdomain of an enabled host
  - Reject lookalike hosts (e.g. weworkremotely.com.evil.io)
  - Normalise: lowercase, strip trailing dot
  - Sites with kind="own" are excluded (checked via is_own_url() instead)
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

_DEFAULT_ALLOWLIST_PATH = Path(__file__).parent / "allowed_sites.json"


@lru_cache(maxsize=None)
def _load_allowlist_cached(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_allowlist() -> dict:
    """
    Return the parsed allowlist dict.  Cached per path.

    Path resolution order:
      1. CV_AGENT_ALLOWED_SITES env var (absolute path)
      2. agent/allowed_sites.json (default)
    """
    env_path = os.environ.get("CV_AGENT_ALLOWED_SITES", "").strip()
    path = env_path if env_path else str(_DEFAULT_ALLOWLIST_PATH)
    return _load_allowlist_cached(path)


def site_names() -> list[str]:
    """Return sorted list of enabled, searchable site names (excludes own site)."""
    data = load_allowlist()
    return sorted(
        name
        for name, cfg in data["sites"].items()
        if cfg.get("enabled", False) and cfg.get("kind") != "own"
    )


def host_for(site: str) -> str:
    """Return the canonical host for a site name. Raises KeyError if unknown."""
    data = load_allowlist()
    return data["sites"][site]["host"].lower()


def own_base_url() -> str:
    """Return the base URL for our own apply site (strips trailing slash)."""
    return os.environ.get("OWN_SITE_BASE_URL", "http://127.0.0.1:5000").rstrip("/")


def own_job_url(job_id: str) -> str:
    """Return the full URL for a job posting on our own site."""
    return f"{own_base_url()}/jobs/{job_id}"


def own_apply_url(job_id: str) -> str:
    """Return the full URL for the apply page on our own site."""
    return f"{own_base_url()}/apply/{job_id}"


def is_own_url(url: str) -> bool:
    """Return True if the URL belongs to our own apply site."""
    if not url:
        return False
    base = own_base_url()
    return url.startswith(base + "/")


def is_url_allowed(url: str) -> bool:
    """
    Return True only if the URL is a valid, allowlisted https URL.

    Checks performed:
      1. Scheme must be https (lowercase after normalisation).
      2. No userinfo (e.g. https://evil@trusted.com is rejected).
      3. Host (after stripping trailing dot, lowercase) must exactly equal
         an enabled site's host OR be a proper subdomain of it.
      4. Reject lookalike suffixes (e.g. .evil.io appended to a real host).
      5. Sites with kind="own" are skipped (use is_own_url() for those).
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # 1. https only
    if parsed.scheme.lower() != "https":
        return False

    # 2. Reject userinfo (username or password in URL)
    if parsed.username is not None or parsed.password is not None:
        return False

    # Normalise host
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False

    # 3 & 4. Host must exactly match or be a proper subdomain
    data = load_allowlist()
    for cfg in data["sites"].values():
        if not cfg.get("enabled", False):
            continue
        if cfg.get("kind") == "own":
            continue
        allowed_host = cfg["host"].lower().rstrip(".")
        if host == allowed_host:
            return True
        # Subdomain: host must end with "." + allowed_host
        if host.endswith("." + allowed_host):
            return True

    return False


def url_belongs_to_site(url: str, site: str) -> bool:
    """
    Return True if the URL's host belongs to the given site name.

    Uses the same host-matching rules as is_url_allowed() but for a
    specific named site rather than any enabled site.
    """
    if not url:
        return False

    data = load_allowlist()
    site_cfg = data["sites"].get(site)
    if site_cfg is None or not site_cfg.get("enabled", False):
        return False
    if site_cfg.get("kind") == "own":
        return False

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme.lower() != "https":
        return False
    if parsed.username is not None or parsed.password is not None:
        return False

    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False

    allowed_host = site_cfg["host"].lower().rstrip(".")
    return host == allowed_host or host.endswith("." + allowed_host)
