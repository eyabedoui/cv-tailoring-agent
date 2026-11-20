"""
Tests for Task D injection additions:
  - i06, i07, i08 JSON files load with required fields
  - seed_injection() copies posting subfields into postings_dir
  - static export HTML-escapes injection titles and text (i07 script tag, i08 linkedin URL)
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INJECTION_DIR = ROOT / "eval" / "injection"


# ---- JSON schema of new injection files -----------------------------------

@pytest.mark.parametrize("fname", [
    "i06_french_arabic_injection.json",
    "i07_search_title_injection.json",
    "i08_linkedin_redirect_injection.json",
])
def test_injection_file_exists(fname):
    assert (INJECTION_DIR / fname).exists()


@pytest.mark.parametrize("fname", [
    "i06_french_arabic_injection.json",
    "i07_search_title_injection.json",
    "i08_linkedin_redirect_injection.json",
])
def test_injection_file_has_required_keys(fname):
    data = json.loads((INJECTION_DIR / fname).read_text(encoding="utf-8"))
    for key in ("id", "category", "job_id", "posting", "decisions",
                "expected_stop_reasons", "expect_submitted", "forbidden_text"):
        assert key in data, f"missing key {key!r} in {fname}"


@pytest.mark.parametrize("fname", [
    "i06_french_arabic_injection.json",
    "i07_search_title_injection.json",
    "i08_linkedin_redirect_injection.json",
])
def test_injection_file_category_is_injection(fname):
    data = json.loads((INJECTION_DIR / fname).read_text(encoding="utf-8"))
    assert data["category"] == "injection"


@pytest.mark.parametrize("fname", [
    "i06_french_arabic_injection.json",
    "i07_search_title_injection.json",
    "i08_linkedin_redirect_injection.json",
])
def test_injection_file_expect_submitted_false(fname):
    data = json.loads((INJECTION_DIR / fname).read_text(encoding="utf-8"))
    assert data["expect_submitted"] is False


@pytest.mark.parametrize("fname,expected_pwned", [
    ("i06_french_arabic_injection.json", "PWNED-906"),
    ("i07_search_title_injection.json", "PWNED-907"),
    ("i08_linkedin_redirect_injection.json", "PWNED-908"),
])
def test_injection_file_has_pwned_marker(fname, expected_pwned):
    data = json.loads((INJECTION_DIR / fname).read_text(encoding="utf-8"))
    assert expected_pwned in data["forbidden_text"]


@pytest.mark.parametrize("fname,expected_job_id", [
    ("i06_french_arabic_injection.json", "job_906"),
    ("i07_search_title_injection.json", "job_907"),
    ("i08_linkedin_redirect_injection.json", "job_908"),
])
def test_injection_posting_job_id_matches(fname, expected_job_id):
    data = json.loads((INJECTION_DIR / fname).read_text(encoding="utf-8"))
    assert data["posting"]["job_id"] == expected_job_id
    assert data["job_id"] == expected_job_id


# ---- seed_injection() -------------------------------------------------------

def test_seed_injection_creates_posting_files(tmp_path):
    from sandbox.manage import seed_injection
    seed_injection(injection_dir=str(INJECTION_DIR), postings_dir=str(tmp_path / "postings"))
    for job_id in ("job_901", "job_902", "job_903", "job_904", "job_905",
                   "job_906", "job_907", "job_908"):
        assert (tmp_path / "postings" / f"{job_id}.json").exists(), f"missing {job_id}.json"


def test_seed_injection_posting_is_valid_json(tmp_path):
    from sandbox.manage import seed_injection
    seed_injection(injection_dir=str(INJECTION_DIR), postings_dir=str(tmp_path / "postings"))
    p = tmp_path / "postings" / "job_906.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["job_id"] == "job_906"


def test_seed_injection_posting_has_required_fields(tmp_path):
    from sandbox.manage import seed_injection
    seed_injection(injection_dir=str(INJECTION_DIR), postings_dir=str(tmp_path / "postings"))
    for job_id in ("job_906", "job_907", "job_908"):
        data = json.loads((tmp_path / "postings" / f"{job_id}.json").read_text(encoding="utf-8"))
        for field in ("job_id", "title", "company", "requirements", "text"):
            assert field in data, f"missing {field!r} in {job_id}"


def test_seed_injection_creates_postings_dir_if_missing(tmp_path):
    from sandbox.manage import seed_injection
    dest = tmp_path / "new_postings"
    assert not dest.exists()
    seed_injection(injection_dir=str(INJECTION_DIR), postings_dir=str(dest))
    assert dest.exists()


# ---- static export HTML-escaping of injection content ----------------------

def test_export_i07_title_script_tag_escaped(tmp_path):
    """i07 title contains <script>; it must be HTML-escaped in the static export."""
    from sandbox.manage import seed_injection, export_static
    seed_injection(injection_dir=str(INJECTION_DIR), postings_dir=str(tmp_path / "postings"))
    export_static(dest=str(tmp_path / "site"), postings_dir=str(tmp_path / "postings"))
    html = (tmp_path / "site" / "jobs" / "job_907.html").read_text(encoding="utf-8")
    assert "<script>" not in html, "raw <script> tag must not appear in export"
    assert "&lt;script&gt;" in html


def test_export_i07_title_injection_text_in_page(tmp_path):
    """i07 title injection text appears in the page (escaped, not executed)."""
    from sandbox.manage import seed_injection, export_static
    seed_injection(injection_dir=str(INJECTION_DIR), postings_dir=str(tmp_path / "postings"))
    export_static(dest=str(tmp_path / "site"), postings_dir=str(tmp_path / "postings"))
    html = (tmp_path / "site" / "jobs" / "job_907.html").read_text(encoding="utf-8")
    # SYSTEM injection text visible in source but not executable
    assert "SYSTEM" in html
    # script tags are escaped
    assert "<script>" not in html


def test_export_i08_linkedin_url_escaped(tmp_path):
    """i08 text contains a linkedin.com URL; it must appear as text, not a live script."""
    from sandbox.manage import seed_injection, export_static
    seed_injection(injection_dir=str(INJECTION_DIR), postings_dir=str(tmp_path / "postings"))
    export_static(dest=str(tmp_path / "site"), postings_dir=str(tmp_path / "postings"))
    html = (tmp_path / "site" / "jobs" / "job_908.html").read_text(encoding="utf-8")
    assert "linkedin.com" in html   # the URL text is present
    assert "<script>" not in html   # but no injected scripts


def test_export_i06_includes_non_ascii_text(tmp_path):
    """i06 posting contains Arabic/French characters; they must appear in the HTML output."""
    from sandbox.manage import seed_injection, export_static
    seed_injection(injection_dir=str(INJECTION_DIR), postings_dir=str(tmp_path / "postings"))
    export_static(dest=str(tmp_path / "site"), postings_dir=str(tmp_path / "postings"))
    html = (tmp_path / "site" / "jobs" / "job_906.html").read_text(encoding="utf-8")
    assert "Atlas Data" in html


def test_export_all_new_injection_pages_exist(tmp_path):
    from sandbox.manage import seed_injection, export_static
    seed_injection(injection_dir=str(INJECTION_DIR), postings_dir=str(tmp_path / "postings"))
    export_static(dest=str(tmp_path / "site"), postings_dir=str(tmp_path / "postings"))
    for job_id in ("job_906", "job_907", "job_908"):
        assert (tmp_path / "site" / "jobs" / f"{job_id}.html").exists()


def test_export_injection_postings_appear_in_index(tmp_path):
    from sandbox.manage import seed_injection, export_static
    seed_injection(injection_dir=str(INJECTION_DIR), postings_dir=str(tmp_path / "postings"))
    export_static(dest=str(tmp_path / "site"), postings_dir=str(tmp_path / "postings"))
    index_html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    for job_id in ("job_906", "job_907", "job_908"):
        assert f"{job_id}.html" in index_html
