"""
Real implementations of the four read tools:
read_job_posting, read_master_cv, match_skills, check_format.

Each function accepts optional injection parameters for test isolation;
when called through execute_tool those parameters are absent and the
module-level defaults (pointing to sandbox/) are used.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Callable

from agent.config import SANDBOX_DIR
from agent.errors import make_error, NOT_FOUND, EMPTY_POSTING, SITE_NOT_ALLOWED

# ---------------------------------------------------------------------------
# Module-level defaults — replace via monkeypatch in tests
# ---------------------------------------------------------------------------

_client_instance = None
_cv_path: Path | None = None


def _get_client():
    global _client_instance
    if _client_instance is None:
        import os
        mode = os.environ.get("WEB_MODE", "fake").lower().strip()
        if mode == "live":
            from agent.tools.clients import FirecrawlPostingClient
            _client_instance = FirecrawlPostingClient()
        else:
            from agent.tools.clients import FakePostingClient
            _client_instance = FakePostingClient()
    return _client_instance


def _get_cv_path() -> Path:
    global _cv_path
    if _cv_path is None:
        _cv_path = Path(SANDBOX_DIR) / "master_cv.md"
    return _cv_path


# ---------------------------------------------------------------------------
# Skill aliases: map a lowercase requirement to alternative phrasings.
# Includes French aliases for Tunisian job boards (W4b).
# ---------------------------------------------------------------------------

_SKILL_ALIASES: dict[str, list[str]] = {
    "javascript": ["js"],
    "typescript": ["ts"],
    "python": ["python3"],
    "sql": ["mysql", "postgresql", "sqlite", "postgres"],
    "unit testing": ["pytest", "jest", "unittest", "mocha", "jasmine", "tests unitaires"],
    "version control": ["git", "svn", "contrôle de version"],
    "data analysis": ["data analytics", "pandas", "analyse de données", "analyse des données"],
    "machine learning": ["scikit-learn", "sklearn", "ml", "apprentissage automatique"],
    "apprentissage automatique": ["machine learning", "ml", "scikit-learn", "sklearn"],
    "natural language processing": ["nlp", "traitement du langage naturel"],
    "traitement du langage naturel": ["nlp", "natural language processing"],
    "rest api": ["rest apis", "restful", "api rest"],
    "rest apis": ["rest api", "restful", "api rest"],
    "continuous integration": ["ci/cd", "github actions", "jenkins"],
    "node.js": ["nodejs", "node js"],
    "html/css": ["html", "css"],
    "problem solving": ["problem-solving", "résolution de problèmes"],
    "résolution de problèmes": ["problem solving", "problem-solving"],
    "communication": [
        "written and verbal communication",
        "verbal communication",
        "communication écrite",
        "communication verbale",
    ],
    "communication écrite": ["communication", "written and verbal communication"],
    "communication verbale": ["communication", "verbal communication"],
    "teamwork": ["travail en équipe", "esprit d'équipe", "team work", "work in a team"],
    "travail en équipe": ["teamwork", "team work"],
    "esprit d'équipe": ["teamwork", "teamwork"],
    "api": ["rest api", "graphql", "web api"],
    # Bidirectional EN ↔ FR language / domain pairs
    "english": ["anglais", "anglais courant", "anglais professionnel"],
    "anglais": ["english"],
    "anglais courant": ["english"],
    "anglais professionnel": ["english"],
    "computer science": ["informatique", "sciences informatiques"],
    "informatique": ["computer science"],
    "sciences informatiques": ["computer science"],
    "database": ["base de données", "bases de données"],
    "base de données": ["database"],
    "bases de données": ["database"],
    "analyse de données": ["data analysis", "data analytics"],
    "analyse des données": ["data analysis", "data analytics"],
}


# ---------------------------------------------------------------------------
# Short-term extraction helpers
# ---------------------------------------------------------------------------

# Common filler prefixes stripped before treating bullet text as a skill term
_FILLER_RE = re.compile(
    r"^(?:"
    r"(?:strong\s+)?"
    r"(?:experience|knowledge|familiarity|understanding|proficiency|expertise|skills?)"
    r"(?:\s+(?:in|with|of|using))?"
    r"|ability\s+to\s+"
    r"|working\s+knowledge\s+of\s+"
    r"|\d+\+?\s+years?\s+(?:of\s+)?(?:experience\s+(?:with\s+|in\s+)?)?"
    r")\s*",
    re.IGNORECASE,
)
_SPLIT_RE = re.compile(r"\s+(?:and|or|,|\/)\s+", re.IGNORECASE)


def _extract_short_terms(raw: str) -> list[str]:
    """
    Convert a raw bullet text into one or more short skill terms.

    E.g. "Experience with Python and machine learning" → ["Python", "machine learning"]
    """
    text = _FILLER_RE.sub("", raw).strip()
    if not text:
        return []
    parts = _SPLIT_RE.split(text)
    result = []
    for part in parts:
        part = part.strip().rstrip(".,;")
        if 1 < len(part) <= 60:
            result.append(part)
    return result or [raw.strip()]


# ---------------------------------------------------------------------------
# parse_posting — convert scraped markdown into the standard posting dict
# ---------------------------------------------------------------------------

def parse_posting(markdown: str, url: str, _extractor: Callable[[str], list[str]] | None = None) -> dict:
    """
    Extract job posting fields from scraped markdown.

    Handles the own-site format produced by _posting_to_markdown and does
    best-effort extraction from external pages.
    """
    from urllib.parse import urlparse
    from agent.sites import is_own_url, url_belongs_to_site, site_names

    lines = markdown.splitlines()

    # Title: first level-1 heading
    title = ""
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip()
            break

    # Company: **Company:** pattern
    company = ""
    for line in lines:
        m = re.search(r"\*\*Company:\*\*\s*(.+)", line)
        if m:
            company = m.group(1).strip()
            break

    # Requirements: bullets under ## Requirements (or ## Prérequis)
    requirements: list[str] = []
    in_req = False
    for line in lines:
        if re.match(r"^## (Requirements|Prérequis|Skills Required)", line, re.IGNORECASE):
            in_req = True
            continue
        if in_req:
            if line.startswith("## "):
                break
            m = re.match(r"^[-*•]\s+(.+)", line)
            if m:
                raw = m.group(1).strip()
                terms = _extract_short_terms(raw)
                requirements.extend(terms)

    # Text: ## Description (or ## About the Role / ## Responsibilities)
    text_parts: list[str] = []
    in_desc = False
    for line in lines:
        if re.match(r"^## (Description|About the Role|Responsibilities|À propos du poste)", line, re.IGNORECASE):
            in_desc = True
            continue
        if in_desc:
            if line.startswith("## "):
                break
            text_parts.append(line)
    text = "\n".join(text_parts).strip()

    # Fallback: use whole markdown as text if no section found
    if not text:
        text = markdown.strip()

    # If no structured requirements were parsed, try the injectable extractor.
    # The extractor receives the full page text (untrusted) and returns a list of
    # short skill terms.  Its output is validated: only non-empty strings kept.
    if not requirements and _extractor is not None:
        try:
            extracted = _extractor(text or markdown)
            if isinstance(extracted, list):
                requirements = [str(t) for t in extracted if str(t).strip()]
        except Exception:
            pass

    # Build job_id
    if is_own_url(url):
        path = urlparse(url).path.strip("/").split("/")
        job_id = path[-1] if path else "unknown"
    else:
        h = hashlib.sha256(url.encode()).hexdigest()[:8]
        site = "ext"
        for s in site_names():
            if url_belongs_to_site(url, s):
                site = s
                break
        job_id = f"{site}-{h}"

    return {
        "job_id": job_id,
        "title": title,
        "company": company,
        "requirements": requirements,
        "text": text,
    }


# ---------------------------------------------------------------------------
# read_job_posting
# ---------------------------------------------------------------------------

def read_job_posting(url: str, _client=None) -> dict:
    """Fetch a job posting by URL and return its structured data."""
    # Defense-in-depth: re-check allowlist for http/https URLs that reach here
    # (the registry pre-check is the primary gate).
    if url.lower().startswith(("http://", "https://")):
        from agent.sites import is_url_allowed, is_own_url, site_names
        if not is_url_allowed(url) and not is_own_url(url):
            names = ", ".join(sorted(site_names()))
            return make_error(
                SITE_NOT_ALLOWED,
                f"URL is not from an allowed site. Allowed sites: {names}.",
            )

    # Throttle + usage log for live mode
    import os as _os
    _mode = _os.environ.get("WEB_MODE", "fake").lower().strip()
    if _mode == "live" and _client is None:
        from agent.tools.throttle import throttle
        from urllib.parse import urlparse
        throttle(urlparse(url).netloc)

    client = _client if _client is not None else _get_client()
    result = client.fetch(url)

    if _mode == "live" and _client is None:
        from agent.tools.usage_log import log_usage
        status = "success" if "error" not in result else result["error"]
        from urllib.parse import urlparse
        log_usage("read_job_posting", urlparse(url).netloc, status)

    if "error" in result:
        return result

    posting = result.get("_posting")
    if posting is None:
        # Real clients (Firecrawl) return markdown; parse it into a posting dict.
        markdown = result.get("markdown", "")
        if not markdown:
            return make_error(NOT_FOUND, f"Cannot parse posting from URL {url!r}")
        posting = parse_posting(markdown, url)

    if not posting.get("text", "").strip():
        return make_error(EMPTY_POSTING, f"Job posting {posting.get('job_id', url)!r} has no descriptive text")

    return {
        "job_id": posting["job_id"],
        "title": posting["title"],
        "company": posting["company"],
        "requirements": posting["requirements"],
        "text": posting["text"],
    }


# ---------------------------------------------------------------------------
# read_master_cv
# ---------------------------------------------------------------------------

def read_master_cv(_cv_path: Path | None = None) -> dict:
    """Read and parse the candidate's master CV from the sandbox."""
    cv_path = _cv_path if _cv_path is not None else _get_cv_path()

    if not cv_path.exists():
        return make_error(NOT_FOUND, f"Master CV not found at {cv_path!r}")

    text = cv_path.read_text(encoding="utf-8")
    sections = _parse_cv_sections(text)
    return {"text": text, "sections": sections}


def _parse_cv_sections(text: str) -> dict[str, Any]:
    """Split a markdown CV into sections keyed by lowercase heading name."""
    sections: dict[str, Any] = {}
    current: str | None = None
    buf: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip().lower()
            buf = []
        elif line.startswith("# "):
            pass  # skip top-level title
        else:
            if current is not None:
                buf.append(line)

    if current is not None:
        sections[current] = "\n".join(buf).strip()

    return sections


# ---------------------------------------------------------------------------
# match_skills
# ---------------------------------------------------------------------------

def match_skills(cv_text: str, job: dict) -> dict:
    """
    Compare job requirements against the CV text.

    Uses case-insensitive substring matching with a small alias table so
    that, e.g., "unit testing" matches a CV that mentions "pytest".
    """
    requirements: list[str] = job.get("requirements", [])
    if not requirements:
        return {"matched": [], "missing": [], "score": 0.0}

    cv_lower = cv_text.lower()
    matched: list[str] = []
    missing: list[str] = []

    for req in requirements:
        if _skill_present(req.lower(), cv_lower):
            matched.append(req)
        else:
            missing.append(req)

    score = round(len(matched) / len(requirements), 4)
    return {"matched": matched, "missing": missing, "score": score}


def _skill_present(req_lower: str, cv_lower: str) -> bool:
    if _word_match(req_lower, cv_lower):
        return True
    for alias in _SKILL_ALIASES.get(req_lower, []):
        if _word_match(alias.lower(), cv_lower):
            return True
    return False


def _word_match(term: str, text: str) -> bool:
    """Match *term* in *text* as a whole phrase (no alphanumeric char on either side)."""
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(term) + r"(?![a-zA-Z0-9])"
    return bool(re.search(pattern, text))


# ---------------------------------------------------------------------------
# check_format
# ---------------------------------------------------------------------------

def check_format(cv_text: str) -> dict:
    """
    Check the CV for basic formatting issues.

    Currently flags only lines that exceed 160 characters.
    Returns ok=True with an empty issues list when no problems are found.
    """
    issues: list[str] = []
    for i, line in enumerate(cv_text.splitlines(), start=1):
        if len(line) > 160:
            issues.append(f"Line {i} exceeds 160 characters ({len(line)} chars)")
    return {"ok": len(issues) == 0, "issues": issues}
