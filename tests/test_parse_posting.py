"""
Tests for parse_posting() and the W4b match_skills upgrades.

All tests are offline — no network, no real Firecrawl calls.
"""
import pytest

from agent.tools.reads import parse_posting, match_skills
from agent.sites import own_job_url


# ---------------------------------------------------------------------------
# parse_posting — own-site markdown format
# ---------------------------------------------------------------------------

_OWN_MARKDOWN = """\
# Senior Python Developer
**Company:** Acme Corp

## Requirements
- Python
- SQL
- Git

## Description
Build backend services using Python and SQL.
"""


def test_parse_own_site_title():
    posting = parse_posting(_OWN_MARKDOWN, own_job_url("job_042"))
    assert posting["title"] == "Senior Python Developer"


def test_parse_own_site_company():
    posting = parse_posting(_OWN_MARKDOWN, own_job_url("job_042"))
    assert posting["company"] == "Acme Corp"


def test_parse_own_site_requirements():
    posting = parse_posting(_OWN_MARKDOWN, own_job_url("job_042"))
    assert posting["requirements"] == ["Python", "SQL", "Git"]


def test_parse_own_site_text():
    posting = parse_posting(_OWN_MARKDOWN, own_job_url("job_042"))
    assert "Build backend services" in posting["text"]


def test_parse_own_site_job_id_from_url():
    posting = parse_posting(_OWN_MARKDOWN, own_job_url("job_042"))
    assert posting["job_id"] == "job_042"


# ---------------------------------------------------------------------------
# parse_posting — external URL (keejob)
# ---------------------------------------------------------------------------

_EXT_MARKDOWN = """\
# Data Engineer
**Company:** DataFlow

## Requirements
- Spark
- Hadoop
- Python

## Description
Join our data team to build scalable pipelines.
"""

_KEEJOB_URL = "https://www.keejob.com/offres-emploi/12345"


def test_parse_external_title():
    posting = parse_posting(_EXT_MARKDOWN, _KEEJOB_URL)
    assert posting["title"] == "Data Engineer"


def test_parse_external_company():
    posting = parse_posting(_EXT_MARKDOWN, _KEEJOB_URL)
    assert posting["company"] == "DataFlow"


def test_parse_external_requirements():
    posting = parse_posting(_EXT_MARKDOWN, _KEEJOB_URL)
    assert "Spark" in posting["requirements"]


def test_parse_external_job_id_format():
    posting = parse_posting(_EXT_MARKDOWN, _KEEJOB_URL)
    assert posting["job_id"].startswith("keejob-")
    assert len(posting["job_id"]) == len("keejob-") + 8


def test_parse_external_job_id_is_deterministic():
    p1 = parse_posting(_EXT_MARKDOWN, _KEEJOB_URL)
    p2 = parse_posting(_EXT_MARKDOWN, _KEEJOB_URL)
    assert p1["job_id"] == p2["job_id"]


def test_parse_external_different_urls_give_different_ids():
    p1 = parse_posting(_EXT_MARKDOWN, "https://www.keejob.com/offres-emploi/11111")
    p2 = parse_posting(_EXT_MARKDOWN, "https://www.keejob.com/offres-emploi/22222")
    assert p1["job_id"] != p2["job_id"]


# ---------------------------------------------------------------------------
# parse_posting — edge cases
# ---------------------------------------------------------------------------

def test_parse_no_heading_returns_empty_title():
    posting = parse_posting("Just some text.\nNo headings here.", "https://www.keejob.com/x")
    assert posting["title"] == ""


def test_parse_no_requirements_returns_empty_list():
    md = "# Job\n**Company:** X\n## Description\nSome text."
    posting = parse_posting(md, "https://www.keejob.com/x")
    assert posting["requirements"] == []


def test_parse_no_description_uses_fallback_text():
    md = "# Job\n**Company:** X\n## Requirements\n- Python"
    posting = parse_posting(md, "https://www.keejob.com/x")
    assert posting["text"] != ""


def test_parse_requirements_with_star_bullets():
    md = "# Dev\n**Company:** Co\n## Requirements\n* Java\n* Spring\n## Description\nText."
    posting = parse_posting(md, own_job_url("job_010"))
    assert "Java" in posting["requirements"]
    assert "Spring" in posting["requirements"]


# ---------------------------------------------------------------------------
# W4b — match_skills word boundaries
# ---------------------------------------------------------------------------

def test_match_skills_git_not_matched_in_digital():
    cv = "I love digital marketing and design."
    job = {"requirements": ["Git"]}
    result = match_skills(cv, job)
    assert "Git" in result["missing"]


def test_match_skills_git_matched_as_whole_word():
    cv = "Proficient in Git and GitHub."
    job = {"requirements": ["Git"]}
    result = match_skills(cv, job)
    assert "Git" in result["matched"]


def test_match_skills_sql_not_matched_in_nosql():
    cv = "Experience with NoSQL databases."
    job = {"requirements": ["SQL"]}
    result = match_skills(cv, job)
    assert "SQL" in result["missing"]


def test_match_skills_sql_matched_standalone():
    cv = "Expertise in SQL and data modeling."
    job = {"requirements": ["SQL"]}
    result = match_skills(cv, job)
    assert "SQL" in result["matched"]


def test_match_skills_python_matched():
    cv = "5 years of Python development."
    job = {"requirements": ["Python"]}
    result = match_skills(cv, job)
    assert "Python" in result["matched"]


# ---------------------------------------------------------------------------
# W4b — French aliases in match_skills
# ---------------------------------------------------------------------------

def test_french_alias_tests_unitaires():
    cv = "Maîtrise des tests unitaires avec pytest."
    job = {"requirements": ["Unit Testing"]}
    result = match_skills(cv, job)
    assert "Unit Testing" in result["matched"]


def test_french_alias_analyse_de_donnees():
    cv = "Expertise en analyse de données et visualisation."
    job = {"requirements": ["Data Analysis"]}
    result = match_skills(cv, job)
    assert "Data Analysis" in result["matched"]


def test_french_alias_resolution_de_problemes():
    cv = "Forte capacité de résolution de problèmes."
    job = {"requirements": ["Problem Solving"]}
    result = match_skills(cv, job)
    assert "Problem Solving" in result["matched"]


def test_french_alias_travail_en_equipe():
    cv = "Esprit de travail en équipe développé."
    job = {"requirements": ["Teamwork"]}
    result = match_skills(cv, job)
    assert "Teamwork" in result["matched"]


def test_french_alias_api_rest():
    cv = "Développement d'API REST avec Flask."
    job = {"requirements": ["Rest API"]}
    result = match_skills(cv, job)
    assert "Rest API" in result["matched"]
