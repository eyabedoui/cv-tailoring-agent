"""
Fabrication checker v1 (C4) + parser accuracy helper (C5).

check_fabrication(master_cv_text, tailored_text) returns a list of
{"type": "skill" | "employer" | "degree", "item": str} for things that appear in
the tailored text but not in the master CV. An empty list means no fabrication found.

v1 checks three things:
  skills     - known tech terms (built-in list + sandbox/missing_skills.md)
  employers  - organisation names (Inc/Corp/Labs/University...) plus a short list of big names
  degrees    - bachelor / master / MBA / PhD level words
Harder cases (inflated level, invented numbers, changed dates) are C7.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Callable

_SANDBOX = Path(__file__).resolve().parent.parent / "sandbox"

EXTRA_SKILL_TERMS = [
    "Kubernetes", "Docker", "AWS", "Azure", "Google Cloud", "GCP", "Terraform", "Ansible",
    "Jenkins", "Rust", "Go", "Scala", "Java", "C++", "C#", "Ruby", "PHP", "Swift", "Kotlin",
    "TypeScript", "Kafka", "Spark", "Hadoop", "Airflow", "Snowflake", "TensorFlow", "PyTorch",
    "Keras", "scikit-learn", "machine learning", "deep learning", "NLP", "Redis", "MongoDB",
    "MySQL", "GraphQL", "Angular", "Vue", "Django", "FastAPI", "Tableau", "Power BI",
    "Selenium", "Spring Boot", ".NET",
]

KNOWN_ORGS = [
    "Google", "Amazon", "Microsoft", "Meta", "Facebook", "Apple", "Netflix", "IBM", "Oracle",
    "Tesla", "OpenAI", "Anthropic", "Nvidia", "Intel", "Samsung", "Uber", "Airbnb", "Spotify",
    "SAP", "Deloitte", "McKinsey",
]

_ORG_SUFFIXES = ["Inc", "Corp", "Corporation", "Ltd", "LLC", "GmbH", "Labs", "Technologies",
                 "Solutions", "University", "Institute", "College"]
_ORG_RE = re.compile(
    r"\b((?:[A-Z][A-Za-z0-9&.\-]*[ \t]+){1,3}(?:" + "|".join(_ORG_SUFFIXES) + r"))\b"
)

_DEGREE_PATTERNS = {
    "bachelor": r"\bBachelor(?:'s|\u2019s)?\b|\bB\.?Sc\b|\bBEng\b",
    "master": r"\bMaster(?:'s|\u2019s)?[ \t]+(?:of|degree|in)\b|\bMasters[ \t]+degree\b|\bM\.?Sc\b|\bMEng\b",
    "mba": r"\bMBA\b",
    "phd": r"\bPh\.?D\b|\bDoctorate\b|\bDoctor of Philosophy\b",
}


# ------------------------------------------------------------------ loading
def load_master_cv_text(path: str | Path | None = None) -> str:
    p = Path(path) if path else _SANDBOX / "master_cv.md"
    return p.read_text(encoding="utf-8")


def load_missing_skills(path: str | Path | None = None) -> list[str]:
    """One skill per line; header and prose lines are skipped."""
    p = Path(path) if path else _SANDBOX / "missing_skills.md"
    if not p.exists():
        return []
    skills = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" in line or line.endswith("."):
            continue
        if len(line.split()) > 4:
            continue
        skills.append(line)
    return skills


# ------------------------------------------------------------------ helpers
@lru_cache(maxsize=None)
def _term_re(term: str, case_sensitive: bool):
    pattern = r"(?<![A-Za-z0-9+#])" + re.escape(term) + r"(?![A-Za-z0-9+#])"
    return re.compile(pattern, 0 if case_sensitive else re.IGNORECASE)


def _find_term(term: str, text: str, case_sensitive: bool | None = None) -> bool:
    if case_sensitive is None:
        case_sensitive = len(term) <= 2  # "Go", "R" must not match the verb "go"
    return _term_re(term, case_sensitive).search(text) is not None


def _norm(text: str) -> str:
    text = re.sub(r"\(fictional\)", " ", text, flags=re.IGNORECASE)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _degree_levels(text: str) -> set[str]:
    return {level for level, pat in _DEGREE_PATTERNS.items()
            if re.search(pat, text, re.IGNORECASE)}


# --------------------------------------------------------------------- main
def check_fabrication(master_cv_text: str, tailored_text: str,
                      missing_skills: list[str] | None = None,
                      allowed=()) -> list[dict]:
    """Return the list of invented items found in tailored_text."""
    if missing_skills is None:
        missing_skills = load_missing_skills()
    flags: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, item: str) -> None:
        key = (kind, item.lower())
        if key not in seen:
            seen.add(key)
            flags.append({"type": kind, "item": item})

    # skills
    for term in dict.fromkeys(EXTRA_SKILL_TERMS + list(missing_skills)):
        if _find_term(term, tailored_text) and not _find_term(term, master_cv_text):
            add("skill", term)

    # employers
    master_norm = _norm(master_cv_text)
    master_orgs = {_norm(m) for m in _ORG_RE.findall(master_cv_text)}
    allowed_norm = [_norm(a) for a in allowed]
    for cand in _ORG_RE.findall(tailored_text):
        n = _norm(cand)
        if n in master_norm or any(m in n for m in master_orgs):
            continue
        if any(a and a in n for a in allowed_norm):
            continue
        add("employer", cand.strip())
    for org in KNOWN_ORGS:
        if _find_term(org, tailored_text, True) and not _find_term(org, master_cv_text, True):
            if not any(_norm(org) in a for a in allowed_norm):
                add("employer", org)

    # degrees
    for level in sorted(_degree_levels(tailored_text) - _degree_levels(master_cv_text)):
        add("degree", level)

    return flags


# ------------------------------------------------------------------ gold labels

def parser_accuracy(
    gold_path: str | Path,
    fetch_fn: Callable[[str], str] | None = None,
) -> dict:
    """
    Evaluate parse_posting() against a gold-label file.

    gold_path: eval/gold/<site>_<name>.json — {url, expected_requirements}
    fetch_fn:  callable(url) -> markdown string.
               If None, loads from sandbox/snapshots/ via FakePostingClient.

    Returns:
        {url, precision, recall, f1, extracted, expected}
    """
    gold = json.loads(Path(gold_path).read_text(encoding="utf-8"))
    url = gold["url"]
    expected_raw: list[str] = gold["expected_requirements"]
    expected = [t.lower() for t in expected_raw]

    if fetch_fn is None:
        from agent.tools.clients import FakePostingClient
        result = FakePostingClient().fetch(url)
        if "error" in result:
            raise RuntimeError(f"Cannot fetch {url}: {result['error']}")
        markdown = result["markdown"]
    else:
        markdown = fetch_fn(url)

    from agent.tools.reads import parse_posting
    posting = parse_posting(markdown, url)
    extracted = [r.lower() for r in posting.get("requirements", [])]

    matched = set(expected) & set(extracted)
    precision = len(matched) / len(extracted) if extracted else 0.0
    recall = len(matched) / len(expected) if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "url": url,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "extracted": extracted,
        "expected": expected,
    }
