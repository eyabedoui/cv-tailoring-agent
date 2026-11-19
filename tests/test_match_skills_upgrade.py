"""
Tests for the upgraded match_skills alias table (W audit item 1).

Covers:
- Bidirectional EN ↔ FR language / domain aliases
- "Java" must NOT match "JavaScript" (word-boundary guard)
- FR-only CV scored against EN requirements
- EN-only CV scored against FR requirements
- Filler-word handling (aliases must not over-match)
- All 25 sandbox postings produce expected scores (from actual function output)
"""

import pytest

from agent.tools.reads import match_skills


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score(cv: str, reqs: list[str]) -> float:
    return match_skills(cv, {"requirements": reqs})["score"]


def _matched(cv: str, reqs: list[str]) -> list[str]:
    return match_skills(cv, {"requirements": reqs})["matched"]


def _missing(cv: str, reqs: list[str]) -> list[str]:
    return match_skills(cv, {"requirements": reqs})["missing"]


# ---------------------------------------------------------------------------
# Core FR ↔ EN bidirectional aliases
# ---------------------------------------------------------------------------

def test_anglais_in_cv_matches_english_requirement():
    """CV in French with 'Anglais courant' must match English requirement."""
    assert _score("Anglais courant, Python, SQL", ["English", "Python", "SQL"]) == 1.0


def test_english_in_cv_matches_anglais_requirement():
    """CV in English must match 'Anglais' requirement."""
    assert _score("English, Python, SQL", ["Anglais", "Python", "SQL"]) == 1.0


def test_anglais_courant_phrase_matches_english_requirement():
    result = match_skills("Maîtrise de l'Anglais courant.", {"requirements": ["English"]})
    assert result["score"] == 1.0


def test_informatique_in_cv_matches_computer_science_requirement():
    assert _score("Informatique, Python", ["computer science", "Python"]) == 1.0


def test_computer_science_in_cv_matches_informatique_requirement():
    assert _score("Computer Science graduate, Python", ["informatique", "Python"]) == 1.0


def test_base_de_donnees_in_cv_matches_database_requirement():
    assert _score("Gestion de base de données, Python", ["database", "Python"]) == 1.0


def test_database_in_cv_matches_base_de_donnees_requirement():
    assert _score("Database design, Python", ["base de données", "Python"]) == 1.0


def test_apprentissage_automatique_in_cv_matches_machine_learning_requirement():
    assert _score("apprentissage automatique, Python", ["machine learning", "Python"]) == 1.0


def test_machine_learning_in_cv_matches_apprentissage_automatique_requirement():
    assert _score("machine learning, Python", ["apprentissage automatique", "Python"]) == 1.0


# ---------------------------------------------------------------------------
# Word-boundary guard: Java must NOT match JavaScript
# ---------------------------------------------------------------------------

def test_java_does_not_match_javascript():
    cv = "JavaScript, React, Python"
    result = match_skills(cv, {"requirements": ["Java"]})
    assert result["score"] == 0.0
    assert "Java" in result["missing"]


def test_javascript_does_not_match_java():
    cv = "Java, Spring Boot"
    result = match_skills(cv, {"requirements": ["JavaScript"]})
    assert result["score"] == 0.0
    assert "JavaScript" in result["missing"]


def test_go_does_not_match_algorithms():
    """Word-boundary: 'Go' must not match 'algorithms' (contains 'go' as substring)."""
    cv = "Data Structures, Algorithms, Python"
    result = match_skills(cv, {"requirements": ["Go"]})
    assert result["score"] == 0.0


def test_sql_does_not_match_nosql():
    """'SQL' must not match 'NoSQL'."""
    cv = "MongoDB, NoSQL, Redis"
    result = match_skills(cv, {"requirements": ["SQL"]})
    assert result["score"] == 0.0


# ---------------------------------------------------------------------------
# French CV vs English requirements (realistic use case)
# ---------------------------------------------------------------------------

def test_french_cv_with_mixed_en_requirements():
    fr_cv = (
        "Python, JavaScript, SQL, HTML/CSS\n"
        "Résolution de problèmes, Travail en équipe, Anglais courant\n"
        "Développement web, Flask, React\n"
        "Git, Linux, Tests unitaires (pytest)"
    )
    result = match_skills(fr_cv, {
        "requirements": [
            "Python", "JavaScript", "SQL", "unit testing",
            "English", "problem solving", "teamwork",
        ]
    })
    assert result["score"] == 1.0


def test_english_cv_with_mixed_fr_requirements():
    en_cv = (
        "Python, machine learning, data analysis\n"
        "Problem solving, teamwork\n"
        "English, SQL, Flask"
    )
    result = match_skills(en_cv, {
        "requirements": [
            "Python", "apprentissage automatique", "analyse de données",
            "résolution de problèmes", "anglais",
        ]
    })
    assert result["score"] == 1.0


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------

def test_empty_requirements_returns_zero():
    result = match_skills("Python, SQL", {"requirements": []})
    assert result["score"] == 0.0
    assert result["matched"] == []
    assert result["missing"] == []


def test_case_insensitive_matching():
    assert _score("PYTHON, SQL", ["python", "sql"]) == 1.0


def test_partial_alias_does_not_over_match():
    """'anglais' alias should not match unrelated words."""
    cv = "Espagnol, Français, Allemand"
    result = match_skills(cv, {"requirements": ["English"]})
    assert result["score"] == 0.0


# ---------------------------------------------------------------------------
# Scores for all 25 sandbox postings (computed from actual function)
# ---------------------------------------------------------------------------

from pathlib import Path
from sandbox.seed import POSTINGS

_MASTER_CV = (Path(__file__).parent.parent / "sandbox" / "master_cv.md").read_text(encoding="utf-8")

_EXPECTED_SCORES: dict[str, float] = {
    "job_001": 0.75,   # Python✓ ML✗ data-analysis✓ problem-solving✓
    "job_002": 1.0,
    "job_003": 0.0,    # Java✗ C++✗ Go✗ Rust✗  (word-boundary: Go ≠ algorithms)
    "job_004": 1.0,
    "job_005": 0.0,
    "job_006": 1.0,
    "job_007": 1.0,
    "job_008": 0.25,   # only Python matches
    "job_009": 0.5,
    "job_010": 0.25,
    "job_011": 1.0,
    "job_012": 0.0,
    "job_013": 1.0,
    "job_014": 1.0,
    "job_015": 1.0,
    "job_016": 0.25,
    "job_017": 1.0,
    "job_018": 0.5,    # Linux✓ Bash✓  Docker✗ Kubernetes✗
    "job_019": 0.75,
    "job_020": 0.25,   # Linux✓  Rust✗ C++✗ Go✗  (word-boundary: Go ≠ algorithms)
    "job_021": 1.0,
    "job_022": 0.75,
    "job_023": 1.0,
    "job_024": 0.75,
    "job_025": 1.0,
}

_POSTING_MAP = {p["job_id"]: p for p in POSTINGS}


@pytest.mark.parametrize("job_id,expected", list(_EXPECTED_SCORES.items()))
def test_posting_score(job_id: str, expected: float):
    posting = _POSTING_MAP[job_id]
    result = match_skills(_MASTER_CV, posting)
    assert result["score"] == expected, (
        f"{job_id}: got {result['score']}, want {expected}. "
        f"matched={result['matched']}, missing={result['missing']}"
    )
