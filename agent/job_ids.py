"""
Job ID utilities for the CV-tailoring agent.

Two forms are valid:
  - Sandbox IDs:  job_NNN  (three decimal digits, e.g. job_001)
  - Live-site IDs: <site>-<8 hex chars>  (e.g. tanitjobs-a1b2c3d4)

make_job_id(site, url) derives the live-site ID deterministically from the
normalised URL using the first 8 hex chars of its SHA-1 digest.

Normalisation steps (same URL must always produce the same ID):
  1. Lowercase scheme and host.
  2. Strip the fragment.
  3. Strip utm_* query parameters.
  4. Remove a trailing slash from the path.
"""

import hashlib
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

_SANDBOX_ID_RE = re.compile(r"^job_\d{3}$")
_SITE_ID_RE = re.compile(r"^[a-z][a-z0-9_-]+-[0-9a-f]{8}$")


def _normalise_url(url: str) -> str:
    """Return a canonical form of the URL for stable ID derivation."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    # Strip utm_* params; sort remaining params for determinism
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in query_params.items() if not k.lower().startswith("utm_")}
    new_query = urlencode(sorted(filtered.items()), doseq=True)
    # Drop fragment entirely
    return urlunparse((scheme, netloc, path, parsed.params, new_query, ""))


def make_job_id(site: str, url: str) -> str:
    """
    Return a stable, site-scoped job ID derived from the posting URL.

    Format: "<site>-<8 hex chars>"
    The 8 hex chars are the first 8 characters of the SHA-1 of the
    normalised URL.
    """
    normalised = _normalise_url(url)
    digest = hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:8]
    return f"{site}-{digest}"


def is_valid_job_id(s: str) -> bool:
    """
    Return True if s is a syntactically valid job ID in either form:
      - Sandbox:   job_NNN
      - Live-site: <site>-<8 hex chars>
    """
    return bool(_SANDBOX_ID_RE.match(s) or _SITE_ID_RE.match(s))
