"""
Tests for scripts/scan_secrets.py — all offline, no network, no real keys.
"""
from pathlib import Path

import pytest

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from scan_secrets import scan_files  # noqa: E402


# ---- clean files -----------------------------------------------------------

def test_empty_file_is_clean(tmp_path):
    f = tmp_path / "empty.py"
    f.write_text("", encoding="utf-8")
    assert scan_files([f]) == []


def test_normal_code_is_clean(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("import os\nprint('hello')\n", encoding="utf-8")
    assert scan_files([f]) == []


def test_env_example_empty_key_is_clean(tmp_path):
    f = tmp_path / ".env.example"
    f.write_text("OPENAI_API_KEY=\nFIRECRAWL_API_KEY=\n", encoding="utf-8")
    assert scan_files([f]) == []


def test_comment_mentioning_key_name_without_assignment_is_clean(tmp_path):
    f = tmp_path / "readme.md"
    f.write_text("# To configure, export OPENAI_API_KEY in your shell.\n", encoding="utf-8")
    assert scan_files([f]) == []


# ---- literal sk- key -------------------------------------------------------

def test_openai_key_detected(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('API_KEY = "sk-proj-abcdefghijklmnopqrst"\n', encoding="utf-8")
    hits = scan_files([f])
    assert len(hits) == 1
    assert hits[0][0] == str(f)
    assert hits[0][1] == 1


def test_openai_key_short_not_detected(tmp_path):
    f = tmp_path / "code.py"
    f.write_text('token = "sk-short"\n', encoding="utf-8")
    assert scan_files([f]) == []


def test_openai_key_redacted_in_output(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('KEY = "sk-proj-abcdefghijklmnopqrst"\n', encoding="utf-8")
    hits = scan_files([f])
    assert hits[0][2].startswith("sk-pro")
    assert "***" in hits[0][2]


# ---- literal fc- key -------------------------------------------------------

def test_firecrawl_key_detected(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('FC_KEY = "fc-xyzabcdefghijklmnopqrstu"\n', encoding="utf-8")
    hits = scan_files([f])
    assert len(hits) == 1


def test_firecrawl_key_short_not_detected(tmp_path):
    f = tmp_path / "code.py"
    f.write_text('label = "fc-tiny"\n', encoding="utf-8")
    assert scan_files([f]) == []


# ---- OPENAI_API_KEY= assignment -------------------------------------------

def test_openai_assignment_detected(tmp_path):
    f = tmp_path / ".env"
    f.write_text("OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrst\n", encoding="utf-8")
    hits = scan_files([f])
    assert len(hits) == 1


def test_openai_assignment_no_value_is_clean(tmp_path):
    f = tmp_path / ".env"
    f.write_text("OPENAI_API_KEY=\n", encoding="utf-8")
    assert scan_files([f]) == []


# ---- FIRECRAWL_API_KEY= assignment ----------------------------------------

def test_firecrawl_assignment_detected(tmp_path):
    f = tmp_path / ".env"
    f.write_text("FIRECRAWL_API_KEY=fc-xyzabcdefghijklmnopqrstu\n", encoding="utf-8")
    hits = scan_files([f])
    assert len(hits) == 1


def test_firecrawl_assignment_no_value_is_clean(tmp_path):
    f = tmp_path / ".env"
    f.write_text("FIRECRAWL_API_KEY=\n", encoding="utf-8")
    assert scan_files([f]) == []


# ---- multiple hits in one file --------------------------------------------

def test_multiple_secrets_in_one_file(tmp_path):
    f = tmp_path / "secrets.py"
    f.write_text(
        'KEY1 = "sk-proj-aaaaaaaaaaaaaaaaaaaa"\n'
        'KEY2 = "fc-bbbbbbbbbbbbbbbbbbbbb"\n',
        encoding="utf-8",
    )
    hits = scan_files([f])
    assert len(hits) == 2


# ---- binary files are skipped ---------------------------------------------

def test_binary_file_skipped(tmp_path):
    f = tmp_path / "image.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"sk-proj-abcdefghijklmnopqrst")
    assert scan_files([f]) == []


# ---- multiple files, only some have hits ----------------------------------

def test_scan_multiple_files_counts_correctly(tmp_path):
    clean = tmp_path / "clean.py"
    clean.write_text("x = 1\n", encoding="utf-8")
    dirty = tmp_path / "dirty.py"
    dirty.write_text('KEY = "sk-proj-aaaaaaaaaaaaaaaaaaaa"\n', encoding="utf-8")
    hits = scan_files([clean, dirty])
    assert len(hits) == 1
    assert hits[0][0] == str(dirty)


# ---- line number is correct -----------------------------------------------

def test_line_number_is_correct(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("x = 1\ny = 2\nKEY = 'sk-proj-aaaaaaaaaaaaaaaaaaaa'\n", encoding="utf-8")
    hits = scan_files([f])
    assert hits[0][1] == 3


# ---- existing repo files are clean (smoke test) ---------------------------

def test_repo_env_example_is_clean():
    env_example = ROOT / ".env.example"
    if env_example.exists():
        assert scan_files([env_example]) == []
