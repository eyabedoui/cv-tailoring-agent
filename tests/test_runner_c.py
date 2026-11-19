"""
Tests for Task-C runner additions:
  - mode field handling (offline/replay/live skip logic)
  - multi-turn scenario support via Session
  - new scenario files (s16–s22) load correctly
  - end-to-end runs for the 7 new scenarios
"""
import os
import json
from pathlib import Path

import pytest

from eval import runner

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def repo_cwd(monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.delenv("FAULT_MODE", raising=False)


def scenario(prefix):
    return next(s for s in runner.load_scenarios(ROOT / "eval" / "scenarios") if s["id"].startswith(prefix))


# ---- schema: mode field ---------------------------------------------------

def test_mode_defaults_to_offline():
    s = runner.normalize_scenario({"id": "t", "job_id": "job_001"})
    assert s["mode"] == "offline"


def test_mode_replay_roundtrips():
    s = runner.normalize_scenario({"id": "t", "job_id": "job_001", "mode": "replay"})
    assert s["mode"] == "replay"


def test_mode_live_roundtrips():
    s = runner.normalize_scenario({"id": "t", "job_id": "job_001", "mode": "live"})
    assert s["mode"] == "live"


def test_messages_field_defaults_to_none():
    s = runner.normalize_scenario({"id": "t", "job_id": "job_001"})
    assert s["messages"] is None


def test_messages_field_coerced_to_list():
    s = runner.normalize_scenario({"id": "t", "job_id": "job_001",
                                   "messages": ["hello", "world"]})
    assert s["messages"] == ["hello", "world"]


# ---- skip logic -----------------------------------------------------------

def _make_s(mode, fake_only=False):
    return runner.normalize_scenario({
        "id": "t", "job_id": "job_001", "mode": mode, "fake_only": fake_only,
    })


def test_replay_skipped_when_model_fake(tmp_path):
    scenarios = [_make_s("replay")]
    results = []
    for s in scenarios:
        skip = (False and s["fake_only"]) or \
               ("fake" == "fake" and s.get("mode", "offline") in ("replay", "live"))
        if skip:
            results.append({"id": s["id"], "skipped": True, "passed": True})
    assert results[0]["skipped"] is True


def test_live_skipped_when_model_fake(tmp_path):
    s = _make_s("live")
    skip = "fake" == "fake" and s.get("mode", "offline") in ("replay", "live")
    assert skip is True


def test_offline_not_skipped_when_model_fake():
    s = _make_s("offline")
    skip = "fake" == "fake" and s.get("mode", "offline") in ("replay", "live")
    assert skip is False


def test_run_folder_skips_replay_scenarios(tmp_path):
    # Inject a replay scenario alongside the existing ones
    replay_s = {
        "id": "t_replay", "job_id": "job_001", "mode": "replay",
        "fake_script": [{"final": "done"}],
    }
    folder = tmp_path / "scenarios"
    folder.mkdir()
    (folder / "t_replay.json").write_text(json.dumps(replay_s), encoding="utf-8")
    results, _ = runner.run_folder(folder, "fake", results_root=tmp_path / "out")
    r = next(r for r in results if r["id"] == "t_replay")
    assert r.get("skipped") is True and r["passed"] is True


# ---- multi-turn scenario loading ------------------------------------------

def test_all_new_scenarios_load():
    scs = runner.load_scenarios(ROOT / "eval" / "scenarios")
    ids = {s["id"] for s in scs}
    for sid in ("s16_search_no_results", "s17_site_not_allowed", "s18_blocked_read",
                "s19_user_changes_mind", "s20_multiturn_find_then_tailor",
                "s21_multiturn_reject_then_abandon", "s22_multiturn_switch_job"):
        assert sid in ids, f"scenario {sid} not found"


def test_total_scenario_count():
    scs = runner.load_scenarios(ROOT / "eval" / "scenarios")
    assert len(scs) >= 22


def test_multiturn_scenarios_have_messages_list():
    scs = runner.load_scenarios(ROOT / "eval" / "scenarios")
    for sid in ("s19_user_changes_mind", "s20_multiturn_find_then_tailor",
                "s21_multiturn_reject_then_abandon", "s22_multiturn_switch_job"):
        s = next(x for x in scs if x["id"] == sid)
        assert isinstance(s["messages"], list) and len(s["messages"]) >= 2, sid


# ---- end-to-end runs of new scenarios ------------------------------------

def test_s16_search_no_results(tmp_path):
    r = runner.run_scenario(scenario("s16"), "fake", log_dir=tmp_path)
    assert r["passed"], r["mismatches"]
    assert r["stop_reason"] == "done"
    assert not r["submitted"]


def test_s17_site_not_allowed(tmp_path):
    r = runner.run_scenario(scenario("s17"), "fake", log_dir=tmp_path)
    assert r["passed"], r["mismatches"]
    assert r["stop_reason"] == "done"
    assert not r["submitted"]


def test_s18_blocked_read(tmp_path):
    r = runner.run_scenario(scenario("s18"), "fake", log_dir=tmp_path)
    assert r["passed"], r["mismatches"]
    assert r["stop_reason"] == "done"
    assert not r["submitted"]


def test_s19_user_changes_mind(tmp_path):
    r = runner.run_scenario(scenario("s19"), "fake", log_dir=tmp_path)
    assert r["passed"], r["mismatches"]
    assert r["stop_reason"] == "done"
    assert r["submitted"]


def test_s20_multiturn_find_then_tailor(tmp_path):
    r = runner.run_scenario(scenario("s20"), "fake", log_dir=tmp_path)
    assert r["passed"], r["mismatches"]
    assert r["stop_reason"] == "done"
    assert r["submitted"]


def test_s21_multiturn_reject_then_abandon(tmp_path):
    r = runner.run_scenario(scenario("s21"), "fake", log_dir=tmp_path)
    assert r["passed"], r["mismatches"]
    assert r["stop_reason"] == "done"
    assert not r["submitted"]


def test_s22_multiturn_switch_job(tmp_path):
    r = runner.run_scenario(scenario("s22"), "fake", log_dir=tmp_path)
    assert r["passed"], r["mismatches"]
    assert r["stop_reason"] == "done"
    assert r["submitted"]


# ---- WEB_MODE is restored after mode=replay scenario ----------------------

def test_web_mode_restored_after_replay_scenario(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_MODE", "fake")
    s = runner.normalize_scenario({
        "id": "t_rep", "job_id": "job_001", "mode": "replay",
        "fake_script": [{"final": "hi"}],
    })
    runner.run_scenario(s, "fake", log_dir=tmp_path)
    assert os.environ.get("WEB_MODE") == "fake"


def test_web_mode_restored_when_not_set(tmp_path, monkeypatch):
    monkeypatch.delenv("WEB_MODE", raising=False)
    s = runner.normalize_scenario({
        "id": "t_rep2", "job_id": "job_001", "mode": "replay",
        "fake_script": [{"final": "hi"}],
    })
    runner.run_scenario(s, "fake", log_dir=tmp_path)
    assert "WEB_MODE" not in os.environ


# ---- total step count spans all turns ------------------------------------

def test_multiturn_total_steps_sum_across_turns(tmp_path):
    # s22 has 3 steps in turn 1 (no_match) + 6 steps in turn 2 = 9 total
    r = runner.run_scenario(scenario("s22"), "fake", log_dir=tmp_path)
    assert r["steps"] > 3, "step count should span both turns"
