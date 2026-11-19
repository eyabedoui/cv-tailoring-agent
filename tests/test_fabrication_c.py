"""
Tests for parser_accuracy (Task C, fabrication.py gold-label extension).
"""
import json
from pathlib import Path

import pytest

from eval.fabrication import parser_accuracy

ROOT = Path(__file__).resolve().parent.parent
GOLD_DIR = ROOT / "eval" / "gold"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "pages"


def _fetch_fixture(name: str):
    """Return a fetch_fn that reads a markdown fixture file."""
    def _fn(url: str) -> str:
        return (FIXTURE_DIR / name).read_text(encoding="utf-8")
    return _fn


# ---- gold file format validation -----------------------------------------

def test_gold_files_exist():
    assert (GOLD_DIR / "tanitjobs_ai_engineer.json").exists()
    assert (GOLD_DIR / "keejob_fullstack.json").exists()


def test_gold_file_has_required_keys():
    for f in GOLD_DIR.glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        assert "url" in data, f"missing url in {f.name}"
        assert "expected_requirements" in data, f"missing expected_requirements in {f.name}"
        assert isinstance(data["expected_requirements"], list), f"expected_requirements not list in {f.name}"
        assert len(data["expected_requirements"]) > 0, f"empty expected_requirements in {f.name}"


def test_gold_urls_are_https():
    for f in GOLD_DIR.glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data["url"].startswith("https://"), f"non-https url in {f.name}"


# ---- parser_accuracy return shape ----------------------------------------

def test_parser_accuracy_returns_dict():
    result = parser_accuracy(
        GOLD_DIR / "tanitjobs_ai_engineer.json",
        fetch_fn=_fetch_fixture("tanitjobs_ai_engineer.md"),
    )
    for key in ("url", "precision", "recall", "f1", "extracted", "expected"):
        assert key in result, f"missing key {key!r}"


def test_parser_accuracy_values_in_range():
    result = parser_accuracy(
        GOLD_DIR / "tanitjobs_ai_engineer.json",
        fetch_fn=_fetch_fixture("tanitjobs_ai_engineer.md"),
    )
    assert 0.0 <= result["precision"] <= 1.0
    assert 0.0 <= result["recall"] <= 1.0
    assert 0.0 <= result["f1"] <= 1.0


def test_parser_accuracy_url_matches_gold():
    result = parser_accuracy(
        GOLD_DIR / "tanitjobs_ai_engineer.json",
        fetch_fn=_fetch_fixture("tanitjobs_ai_engineer.md"),
    )
    gold = json.loads((GOLD_DIR / "tanitjobs_ai_engineer.json").read_text(encoding="utf-8"))
    assert result["url"] == gold["url"]


# ---- precision / recall arithmetic ---------------------------------------

def test_perfect_match_gives_f1_one(tmp_path):
    md = "# Job\n## Requirements\n- Python\n- SQL\n"
    gold = {"url": "https://www.tanitjobs.com/job/1", "expected_requirements": ["Python", "SQL"]}
    gf = tmp_path / "g.json"
    gf.write_text(json.dumps(gold), encoding="utf-8")
    r = parser_accuracy(gf, fetch_fn=lambda url: md)
    assert r["precision"] == 1.0
    assert r["recall"] == 1.0
    assert r["f1"] == 1.0


def test_no_match_gives_zero_scores(tmp_path):
    md = "# Job\n## Requirements\n- Kubernetes\n- Terraform\n"
    gold = {"url": "https://www.tanitjobs.com/job/2", "expected_requirements": ["Python", "SQL"]}
    gf = tmp_path / "g.json"
    gf.write_text(json.dumps(gold), encoding="utf-8")
    r = parser_accuracy(gf, fetch_fn=lambda url: md)
    assert r["recall"] == 0.0


def test_partial_match_precision_recall(tmp_path):
    md = "# Job\n## Requirements\n- Python\n- Kubernetes\n- SQL\n"
    gold = {"url": "https://www.tanitjobs.com/job/3", "expected_requirements": ["Python", "SQL"]}
    gf = tmp_path / "g.json"
    gf.write_text(json.dumps(gold), encoding="utf-8")
    r = parser_accuracy(gf, fetch_fn=lambda url: md)
    # extracted: ["python", "kubernetes", "sql"] (3)
    # expected: ["python", "sql"] (2)
    # matched: {"python", "sql"} (2)
    # precision = 2/3
    # recall = 2/2 = 1.0
    assert r["recall"] == 1.0
    assert r["precision"] == pytest.approx(2 / 3, rel=1e-3)


def test_case_insensitive_matching(tmp_path):
    md = "# Job\n## Requirements\n- PYTHON\n- Sql\n"
    gold = {"url": "https://www.tanitjobs.com/job/4", "expected_requirements": ["python", "SQL"]}
    gf = tmp_path / "g.json"
    gf.write_text(json.dumps(gold), encoding="utf-8")
    r = parser_accuracy(gf, fetch_fn=lambda url: md)
    assert r["recall"] == 1.0


# ---- fixture-based smoke tests -------------------------------------------

def test_tanitjobs_ai_engineer_fixture_nonzero_recall():
    r = parser_accuracy(
        GOLD_DIR / "tanitjobs_ai_engineer.json",
        fetch_fn=_fetch_fixture("tanitjobs_ai_engineer.md"),
    )
    assert r["recall"] > 0.0, f"recall={r['recall']}, extracted={r['extracted']}"


def test_keejob_fullstack_fixture_nonzero_recall():
    r = parser_accuracy(
        GOLD_DIR / "keejob_fullstack.json",
        fetch_fn=_fetch_fixture("keejob_fullstack.md"),
    )
    assert r["recall"] > 0.0, f"recall={r['recall']}, extracted={r['extracted']}"


def test_expected_list_lowercased_in_result(tmp_path):
    md = "# Job\n## Requirements\n- Python\n"
    gold = {"url": "https://www.tanitjobs.com/job/5", "expected_requirements": ["Python"]}
    gf = tmp_path / "g.json"
    gf.write_text(json.dumps(gold), encoding="utf-8")
    r = parser_accuracy(gf, fetch_fn=lambda url: md)
    assert all(e == e.lower() for e in r["expected"])


def test_extracted_list_lowercased_in_result(tmp_path):
    md = "# Job\n## Requirements\n- Python\n- SQL\n"
    gold = {"url": "https://www.tanitjobs.com/job/6", "expected_requirements": ["Python"]}
    gf = tmp_path / "g.json"
    gf.write_text(json.dumps(gold), encoding="utf-8")
    r = parser_accuracy(gf, fetch_fn=lambda url: md)
    assert all(e == e.lower() for e in r["extracted"])
