
"""
Tests for agent/tools/reads.py — read_job_posting, read_master_cv,
match_skills, check_format.

read_job_posting and read_master_cv accept injection parameters for isolation.
match_skills and check_format operate on plain text, no I/O needed.
"""

import json
import textwrap
from pathlib import Path

import pytest

from agent.tools.reads import (
    check_format,
    match_skills,
    read_job_posting,
    read_master_cv,
)
from sandbox.portal import Portal
from sandbox.seed import POSTINGS, seed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seeded_portal(tmp_path: Path) -> Portal:
    seed(postings_dir=tmp_path / "postings")
    return Portal(sandbox_dir=str(tmp_path))


def _write_cv(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "master_cv.md"
    p.write_text(text, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# read_job_posting — happy path
# ---------------------------------------------------------------------------

def test_read_job_posting_returns_correct_job_id(tmp_path):
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert result["job_id"] == "job_001"


def test_read_job_posting_returns_correct_title(tmp_path):
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert result["title"] == "Junior AI Engineer"


def test_read_job_posting_has_requirements_list(tmp_path):
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert isinstance(result["requirements"], list)
    assert len(result["requirements"]) > 0


def test_read_job_posting_has_non_empty_text(tmp_path):
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert len(result["text"]) > 10


def test_read_all_25_job_postings_accessible(tmp_path):
    portal = _seeded_portal(tmp_path)
    for i in range(1, 26):
        result = read_job_posting(f"mock://jobs/job_{i:03d}", _portal=portal)
        assert result.get("job_id") == f"job_{i:03d}", f"job_{i:03d} returned error"


# ---------------------------------------------------------------------------
# read_job_posting — error paths
# ---------------------------------------------------------------------------

def test_read_job_posting_not_found(tmp_path):
    portal = _seeded_portal(tmp_path)
    result = read_job_posting("mock://jobs/job_999", _portal=portal)
    assert result["error"] == "NOT_FOUND"


def test_read_job_posting_empty_text_returns_empty_posting(tmp_path):
    portal = Portal(sandbox_dir=str(tmp_path))
    (tmp_path / "postings").mkdir(parents=True, exist_ok=True)
    posting = {
        "job_id": "job_001",
        "title": "Empty Job",
        "company": "Test Corp",
        "requirements": ["Python"],
        "text": "   ",  # whitespace only
    }
    with open(tmp_path / "postings" / "job_001.json", "w") as fh:
        json.dump(posting, fh)
    result = read_job_posting("mock://jobs/job_001", _portal=portal)
    assert result["error"] == "EMPTY_POSTING"


# ---------------------------------------------------------------------------
# read_master_cv — happy path
# ---------------------------------------------------------------------------

SAMPLE_CV = textwrap.dedent("""\
    # CV — test_candidate

    Jane Smith

    ## Education

    BSc Computer Science, 2024.

    ## Skills

    Python, SQL, pandas

    ## Experience

    Data Analyst Intern, 2023.
""")


def test_read_master_cv_returns_text(tmp_path):
    cv_path = _write_cv(tmp_path, SAMPLE_CV)
    result = read_master_cv(_cv_path=cv_path)
    assert "Python" in result["text"]


def test_read_master_cv_returns_sections_dict(tmp_path):
    cv_path = _write_cv(tmp_path, SAMPLE_CV)
    result = read_master_cv(_cv_path=cv_path)
    assert isinstance(result["sections"], dict)


def test_read_master_cv_sections_has_skills(tmp_path):
    cv_path = _write_cv(tmp_path, SAMPLE_CV)
    result = read_master_cv(_cv_path=cv_path)
    assert "skills" in result["sections"]


def test_read_master_cv_sections_has_education(tmp_path):
    cv_path = _write_cv(tmp_path, SAMPLE_CV)
    result = read_master_cv(_cv_path=cv_path)
    assert "education" in result["sections"]


def test_read_master_cv_sections_has_experience(tmp_path):
    cv_path = _write_cv(tmp_path, SAMPLE_CV)
    result = read_master_cv(_cv_path=cv_path)
    assert "experience" in result["sections"]


def test_read_master_cv_section_text_is_non_empty(tmp_path):
    cv_path = _write_cv(tmp_path, SAMPLE_CV)
    result = read_master_cv(_cv_path=cv_path)
    assert result["sections"]["skills"].strip() != ""


def test_read_master_cv_real_file_has_python():
    """Smoke-test against the real committed sandbox/master_cv.md."""
    result = read_master_cv()
    assert "Python" in result["text"]


# ---------------------------------------------------------------------------
# read_master_cv — error path
# ---------------------------------------------------------------------------

def test_read_master_cv_missing_file_returns_not_found(tmp_path):
    cv_path = tmp_path / "nonexistent.md"
    result = read_master_cv(_cv_path=cv_path)
    assert result["error"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# match_skills — direct matching
# ---------------------------------------------------------------------------

def test_match_skills_all_matched():
    result = match_skills("Python and SQL", {"requirements": ["Python", "SQL"]})
    assert result["score"] == 1.0
    assert result["missing"] == []
    assert set(result["matched"]) == {"Python", "SQL"}


def test_match_skills_none_matched():
    result = match_skills("Python developer", {"requirements": ["Java", "C++"]})
    assert result["score"] == 0.0
    assert result["matched"] == []


def test_match_skills_partial_match():
    result = match_skills("Python developer", {"requirements": ["Python", "Java"]})
    assert result["score"] == 0.5
    assert "Python" in result["matched"]
    assert "Java" in result["missing"]


def test_match_skills_case_insensitive():
    result = match_skills("PYTHON expert", {"requirements": ["python"]})
    assert result["score"] == 1.0


def test_match_skills_empty_requirements():
    result = match_skills("Python developer", {"requirements": []})
    assert result["score"] == 0.0


def test_match_skills_score_between_zero_and_one():
    result = match_skills("some text", {"requirements": ["Python", "Java", "SQL"]})
    assert 0.0 <= result["score"] <= 1.0


# ---------------------------------------------------------------------------
# match_skills — alias matching
# ---------------------------------------------------------------------------

def test_match_skills_unit_testing_alias_pytest():
    result = match_skills("I use pytest for testing", {"requirements": ["unit testing"]})
    assert "unit testing" in result["matched"]


def test_match_skills_unit_testing_alias_jest():
    result = match_skills("frontend tested with Jest", {"requirements": ["unit testing"]})
    assert "unit testing" in result["matched"]


def test_match_skills_data_analysis_alias_pandas():
    result = match_skills("proficient in pandas for data work", {"requirements": ["data analysis"]})
    assert "data analysis" in result["matched"]


def test_match_skills_rest_api_alias_rest_apis():
    result = match_skills("built REST APIs with Flask", {"requirements": ["rest api"]})
    assert "rest api" in result["matched"]


def test_match_skills_problem_solving_alias():
    result = match_skills("strong problem-solving skills", {"requirements": ["problem solving"]})
    assert "problem solving" in result["matched"]


# ---------------------------------------------------------------------------
# match_skills against master_cv.md job_001 requirements
# ---------------------------------------------------------------------------

def test_match_skills_job001_score_is_75_percent():
    """
    job_001 requirements: Python, machine learning, Data analysis, Problem solving
    CV has: Python ✓, machine learning ✗, Data analysis ✓, Problem solving ✓ → 0.75
    """
    cv_result = read_master_cv()
    cv_text = cv_result["text"]
    job = {
        "requirements": ["Python", "machine learning", "Data analysis", "Problem solving"]
    }
    result = match_skills(cv_text, job)
    assert result["score"] == pytest.approx(0.75, abs=0.01)
    assert "machine learning" in result["missing"]


# ---------------------------------------------------------------------------
# check_format
# ---------------------------------------------------------------------------

def test_check_format_ok_for_simple_text():
    result = check_format("Sample CV text")
    assert result["ok"] is True
    assert result["issues"] == []


def test_check_format_ok_for_empty_string():
    result = check_format("")
    assert result["ok"] is True


def test_check_format_flags_line_over_160_chars():
    long_line = "x" * 161
    result = check_format(f"Normal line\n{long_line}\nAnother line")
    assert result["ok"] is False
    assert len(result["issues"]) >= 1
    assert "2" in result["issues"][0]  # line 2


def test_check_format_ok_for_exactly_160_chars():
    line = "x" * 160
    result = check_format(line)
    assert result["ok"] is True


def test_check_format_flags_multiple_long_lines():
    cv = "\n".join(["x" * 161] * 3)
    result = check_format(cv)
    assert len(result["issues"]) == 3


def test_check_format_ok_for_real_master_cv():
    cv_text = read_master_cv()["text"]
    result = check_format(cv_text)
    assert result["ok"] is True
