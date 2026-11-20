"""
Tests for sandbox management hygiene (Fix 1 + Fix 3):
  - create_dirs(), seed(), reset() must never spawn a subprocess
  - eval runner run_folder must never spawn a subprocess
  - seed() must call seed_injection() (injection postings included)
  - After seed() + export_static(), injection pages job_901..job_908 all exist
"""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raise_subprocess(*args, **kwargs):
    raise AssertionError(
        f"subprocess.run should not be called here, but was called with: {args!r}"
    )


# ---------------------------------------------------------------------------
# Fix 1: create_dirs / seed / reset never call subprocess
# ---------------------------------------------------------------------------

def test_create_dirs_never_calls_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _raise_subprocess)
    from sandbox import manage as m
    monkeypatch.setattr(m, "_BASE", tmp_path / "sandbox")
    m.create_dirs()   # must not raise


def test_reset_never_calls_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _raise_subprocess)
    from sandbox import manage as m
    monkeypatch.setattr(m, "_BASE", tmp_path / "sandbox")
    m.reset()   # must not raise


def test_seed_never_calls_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _raise_subprocess)
    import sandbox.seed as _seed_mod
    from sandbox import manage as m
    monkeypatch.setattr(m, "_BASE", tmp_path / "sandbox")
    # Bypass the inner seed and injection so the test focuses on manage.seed
    monkeypatch.setattr(_seed_mod, "seed", lambda postings_dir=None: None)
    monkeypatch.setattr(m, "seed_injection", lambda injection_dir=None, postings_dir=None: None)
    m.seed()   # must not raise


def test_eval_runner_run_folder_never_calls_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _raise_subprocess)
    from eval import runner
    folder = tmp_path / "scenarios"
    folder.mkdir()
    results, _ = runner.run_folder(folder, "fake", results_root=tmp_path / "out")
    assert results == []   # empty folder → no scenarios, no subprocess


# ---------------------------------------------------------------------------
# Fix 3: seed() calls seed_injection()
# ---------------------------------------------------------------------------

def test_seed_calls_seed_injection(tmp_path, monkeypatch):
    import sandbox.seed as _seed_mod
    from sandbox import manage as m
    monkeypatch.setattr(m, "_BASE", tmp_path / "sandbox")
    monkeypatch.setattr(_seed_mod, "seed", lambda postings_dir=None: None)

    called = []
    monkeypatch.setattr(
        m, "seed_injection",
        lambda injection_dir=None, postings_dir=None: called.append(True),
    )
    m.seed()
    assert called, "seed() must call seed_injection()"


# ---------------------------------------------------------------------------
# Fix 3 (integration): after seed() + export_static(), injection pages exist
# ---------------------------------------------------------------------------

def test_seed_then_export_includes_injection_pages(tmp_path, monkeypatch):
    """Full pipeline: seed → export-static must produce job_901..job_908 HTML files."""
    from sandbox import manage as m
    monkeypatch.setattr(m, "_BASE", tmp_path / "sandbox")
    monkeypatch.setattr(subprocess, "run", _raise_subprocess)   # no Playwright

    injection_dir = str(ROOT / "eval" / "injection")
    postings_dir = str(tmp_path / "sandbox" / "postings")

    from sandbox.seed import seed as _inner_seed
    _inner_seed(postings_dir=tmp_path / "sandbox" / "postings")
    m.seed_injection(injection_dir=injection_dir, postings_dir=postings_dir)

    dest = tmp_path / "site"
    m.export_static(dest=str(dest), postings_dir=postings_dir)

    # All 8 injection job pages must exist
    for job_id in ("job_901", "job_902", "job_903", "job_904",
                   "job_905", "job_906", "job_907", "job_908"):
        page = dest / "jobs" / f"{job_id}.html"
        assert page.exists(), f"{job_id}.html missing from export"


def test_seed_then_export_injection_text_is_escaped(tmp_path, monkeypatch):
    """Injection text in titles/text fields must be HTML-escaped in the export."""
    from sandbox import manage as m
    monkeypatch.setattr(m, "_BASE", tmp_path / "sandbox")
    monkeypatch.setattr(subprocess, "run", _raise_subprocess)

    injection_dir = str(ROOT / "eval" / "injection")
    postings_dir = str(tmp_path / "sandbox" / "postings")

    from sandbox.seed import seed as _inner_seed
    _inner_seed(postings_dir=tmp_path / "sandbox" / "postings")
    m.seed_injection(injection_dir=injection_dir, postings_dir=postings_dir)

    dest = tmp_path / "site"
    m.export_static(dest=str(dest), postings_dir=postings_dir)

    # i07 has a <script> tag in its title — it must be escaped
    html = (dest / "jobs" / "job_907.html").read_text(encoding="utf-8")
    assert "<script>" not in html, "raw <script> must be HTML-escaped"
    assert "&lt;script&gt;" in html
