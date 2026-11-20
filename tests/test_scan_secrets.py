"""
Tests for scripts/scan_secrets.py — all offline, no network, no real keys.

Fake keys are built by string concatenation so no literal key-shaped token
sits in this source file (the scanner would otherwise flag this file itself).
"""
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from scan_secrets import scan_files, _EXCLUDED_PATHS  # noqa: E402

# ---------------------------------------------------------------------------
# Fake-key constants — assembled at runtime, not literal key strings.
# The scanner pattern requires 20+ chars after the prefix; keep that length.
# ---------------------------------------------------------------------------
_SK = "sk-" + "proj-abcdefghijklmnopqrst"   # 24 chars after sk-
_FC = "fc-" + "xyzabcdefghijklmnopqrstu"     # 24 chars after fc-
_SK_SHORT = "sk-" + "short"                  # too short — must NOT be flagged


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
    f.write_text(f'API_KEY = "{_SK}"\n', encoding="utf-8")
    hits = scan_files([f])
    assert len(hits) == 1
    assert hits[0][0] == str(f)
    assert hits[0][1] == 1


def test_openai_key_short_not_detected(tmp_path):
    f = tmp_path / "code.py"
    f.write_text(f'token = "{_SK_SHORT}"\n', encoding="utf-8")
    assert scan_files([f]) == []


def test_openai_key_redacted_in_output(tmp_path):
    f = tmp_path / "config.py"
    f.write_text(f'KEY = "{_SK}"\n', encoding="utf-8")
    hits = scan_files([f])
    assert hits[0][2].startswith("sk-pro")
    assert "***" in hits[0][2]


# ---- literal fc- key -------------------------------------------------------

def test_firecrawl_key_detected(tmp_path):
    f = tmp_path / "config.py"
    f.write_text(f'FC_KEY = "{_FC}"\n', encoding="utf-8")
    hits = scan_files([f])
    assert len(hits) == 1


def test_firecrawl_key_short_not_detected(tmp_path):
    f = tmp_path / "code.py"
    f.write_text('label = "fc-tiny"\n', encoding="utf-8")
    assert scan_files([f]) == []


# ---- OPENAI_API_KEY= assignment -------------------------------------------

def test_openai_assignment_detected(tmp_path):
    f = tmp_path / ".env"
    f.write_text(f"OPENAI_API_KEY={_SK}\n", encoding="utf-8")
    hits = scan_files([f])
    assert len(hits) == 1


def test_openai_assignment_no_value_is_clean(tmp_path):
    f = tmp_path / ".env"
    f.write_text("OPENAI_API_KEY=\n", encoding="utf-8")
    assert scan_files([f]) == []


# ---- FIRECRAWL_API_KEY= assignment ----------------------------------------

def test_firecrawl_assignment_detected(tmp_path):
    f = tmp_path / ".env"
    f.write_text(f"FIRECRAWL_API_KEY={_FC}\n", encoding="utf-8")
    hits = scan_files([f])
    assert len(hits) == 1


def test_firecrawl_assignment_no_value_is_clean(tmp_path):
    f = tmp_path / ".env"
    f.write_text("FIRECRAWL_API_KEY=\n", encoding="utf-8")
    assert scan_files([f]) == []


# ---- multiple hits in one file --------------------------------------------

def test_multiple_secrets_in_one_file(tmp_path):
    f = tmp_path / "secrets.py"
    f.write_text(f'KEY1 = "{_SK}"\nKEY2 = "{_FC}"\n', encoding="utf-8")
    hits = scan_files([f])
    assert len(hits) == 2


# ---- binary files are skipped ---------------------------------------------

def test_binary_file_skipped(tmp_path):
    f = tmp_path / "image.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + _SK.encode())
    assert scan_files([f]) == []


# ---- multiple files, only some have hits ----------------------------------

def test_scan_multiple_files_counts_correctly(tmp_path):
    clean = tmp_path / "clean.py"
    clean.write_text("x = 1\n", encoding="utf-8")
    dirty = tmp_path / "dirty.py"
    dirty.write_text(f'KEY = "{_SK}"\n', encoding="utf-8")
    hits = scan_files([clean, dirty])
    assert len(hits) == 1
    assert hits[0][0] == str(dirty)


# ---- line number is correct -----------------------------------------------

def test_line_number_is_correct(tmp_path):
    f = tmp_path / "code.py"
    f.write_text(f"x = 1\ny = 2\nKEY = '{_SK}'\n", encoding="utf-8")
    hits = scan_files([f])
    assert hits[0][1] == 3


# ---- # scan:ignore suppresses a hit ---------------------------------------

def test_scan_ignore_marker_suppresses_hit(tmp_path):
    f = tmp_path / "code.py"
    f.write_text(f'KEY = "{_SK}"  # scan:ignore\n', encoding="utf-8")
    assert scan_files([f]) == []


def test_scan_ignore_only_suppresses_its_own_line(tmp_path):
    f = tmp_path / "code.py"
    f.write_text(
        f'SAFE = "{_SK}"  # scan:ignore\n'
        f'UNSAFE = "{_SK}"\n',
        encoding="utf-8",
    )
    hits = scan_files([f])
    assert len(hits) == 1
    assert hits[0][1] == 2


# ---- excluded paths are skipped -------------------------------------------

def test_excluded_path_is_skipped(tmp_path):
    # Create a file at a path that ends with an excluded suffix
    p = tmp_path / "scripts" / "scan_secrets.py"
    p.parent.mkdir()
    p.write_text(f'KEY = "{_SK}"\n', encoding="utf-8")
    assert scan_files([p]) == []


def test_non_excluded_path_is_scanned(tmp_path):
    p = tmp_path / "other.py"
    p.write_text(f'KEY = "{_SK}"\n', encoding="utf-8")
    hits = scan_files([p])
    assert len(hits) == 1


def test_excluded_paths_set_contains_script_and_test():
    assert any("scan_secrets.py" in e for e in _EXCLUDED_PATHS)
    assert any("test_scan_secrets.py" in e for e in _EXCLUDED_PATHS)


# ---- existing repo files are clean (smoke test) ---------------------------

def test_repo_env_example_is_clean():
    env_example = ROOT / ".env.example"
    if env_example.exists():
        assert scan_files([env_example]) == []
