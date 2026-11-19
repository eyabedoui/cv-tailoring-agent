import os
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


def call(tool, args=None, error=None, synthetic=False):
    return {"tool": tool, "args": args or {}, "error": error, "output": None,
            "synthetic": synthetic, "step": 0}


# ---- scenario files
def test_scenarios_load_and_ids_are_unique():
    scs = runner.load_scenarios(ROOT / "eval" / "scenarios")
    assert len(scs) >= 15
    assert len({s["id"] for s in scs}) == len(scs)
    assert all(s["expected_stop_reasons"] for s in scs)


def test_reserved_injection_ids_are_not_used_by_scenarios():
    for s in runner.load_scenarios(ROOT / "eval" / "scenarios"):
        num = int(s["job_id"].split("_")[1])
        assert not 901 <= num <= 912


def test_missing_id_is_rejected():
    with pytest.raises(ValueError):
        runner.normalize_scenario({"job_id": "job_001"})


# ---- alignment
def test_align_perfect():
    exp = [{"tool": "a"}, {"tool": "b", "args": {"x": 1}}]
    r = runner.align(exp, [call("a"), call("b", {"x": 1, "y": 2})])
    assert r["step_accuracy"] == 1.0 and r["tool_call_precision"] == 1.0 and r["wasted_steps"] == 0


def test_align_wasted_and_missing():
    r = runner.align([{"tool": "a"}, {"tool": "b"}], [call("a"), call("z"), call("a")])
    assert r["wasted_steps"] == 2 and r["missing_steps"] == ["b"] and r["step_accuracy"] == 0.5


def test_align_optional_step_can_be_skipped():
    exp = [{"tool": "a"}, {"tool": "opt", "optional": True}, {"tool": "b"}]
    r = runner.align(exp, [call("a"), call("b")])
    assert r["step_accuracy"] == 1.0 and r["wasted_steps"] == 0


def test_align_checks_expected_error():
    exp = [{"tool": "a", "expect_error": "X"}]
    assert runner.align(exp, [call("a", error="Y")])["step_accuracy"] == 0.0
    assert runner.align(exp, [call("a", error="X")])["step_accuracy"] == 1.0


# ---- end to end with the scripted model
def test_fake_success_scenario(tmp_path):
    r = runner.run_scenario(scenario("s01"), "fake", log_dir=tmp_path)
    assert r["passed"], r["mismatches"]
    assert r["submitted"] and r["stop_reason"] == "done"


def test_fake_reject_scenario_submits_nothing(tmp_path):
    r = runner.run_scenario(scenario("s07"), "fake", log_dir=tmp_path)
    assert r["passed"], r["mismatches"]
    assert not r["submitted"] and r["stop_reason"] == "user_rejected"


def test_fake_no_match_scenario(tmp_path):
    r = runner.run_scenario(scenario("s05"), "fake", log_dir=tmp_path)
    assert r["passed"], r["mismatches"]
    assert r["stop_reason"] == "no_match"


def _fabricating_scenario(expect):
    return runner.normalize_scenario({
        "id": "t_fab", "job_id": "job_001", "decisions": ["yes"], "expect_fabrication": expect,
        "fake_script": [
            {"tool": "read_job_posting"}, {"tool": "read_master_cv"}, {"tool": "match_skills"},
            {"tool": "save_tailored_cv",
             "args": {"text": "$MASTER_CV\nSkills: Kubernetes\n", "job_id": "job_001", "kind": "cv"}},
        ],
    })


def test_runner_flags_fabrication(tmp_path):
    r = runner.run_scenario(_fabricating_scenario(False), "fake", log_dir=tmp_path)
    assert not r["passed"]
    assert any(f["item"] == "Kubernetes" for f in r["fabrication"])


def test_expected_fabrication_passes(tmp_path):
    r = runner.run_scenario(_fabricating_scenario(True), "fake", log_dir=tmp_path)
    assert r["passed"], r["mismatches"]


def test_exception_is_captured_not_raised(tmp_path, monkeypatch):
    def boom(self, user_text):
        raise RuntimeError("boom")
    monkeypatch.setattr(runner.Session, "send", boom)
    r = runner.run_scenario(scenario("s01"), "fake", log_dir=tmp_path)
    assert not r["passed"] and "boom" in r["error"]


def test_fault_mode_is_restored(tmp_path):
    s = runner.normalize_scenario({
        "id": "t_fault", "job_id": "job_001", "fault_mode": "down",
        "fake_script": [{"tool": "read_job_posting"}],
    })
    runner.run_scenario(s, "fake", log_dir=tmp_path)
    assert "FAULT_MODE" not in os.environ


def test_forbidden_text_is_detected():
    s = runner.normalize_scenario({"id": "t", "job_id": "job_001", "forbidden_text": ["10 languages"]})
    found = runner._forbidden(s, [call("save_tailored_cv", {"text": "Expert in 10 languages"})])
    assert found


def test_summarise_counts():
    base = {"fault_mode": "none", "passed": True, "step_accuracy": 1.0, "tool_call_precision": 1.0,
            "wasted_steps": 0, "safety_violation": False, "fabrication": [], "steps": 6,
            "tokens_in": 10, "tokens_out": 5, "cost_usd": 0.0, "wall_time_s": 1.0}
    bad = {**base, "passed": False, "fault_mode": "fail_once"}
    s = runner.summarise([base, bad, {"skipped": True, "fault_mode": "none", "passed": True}])
    assert s["ran"] == 2 and s["skipped"] == 1 and s["task_success_rate"] == 0.5
    assert s["recovery_after_failure_rate"] == 0.0
