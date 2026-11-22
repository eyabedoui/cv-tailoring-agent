"""C6: extra metrics computed from result dicts."""
from eval.runner import extra_metrics


def r(cat="success", passed=True, steps=6, stop="done", tools=()):
    return {"category": cat, "passed": passed, "steps": steps, "stop_reason": stop,
            "trajectory": [{"tool": t, "synthetic": False} for t in tools]}


def test_injection_pass_rate():
    m = extra_metrics([r("injection"), r("injection", passed=False), r()])
    assert m["injection_runs"] == 2 and m["injection_pass_rate"] == 0.5


def test_no_injection_gives_none():
    assert extra_metrics([r()])["injection_pass_rate"] is None


def test_stop_rule_flag():
    assert extra_metrics([r(steps=12)])["stop_rule_never_exceeded"] is True
    assert extra_metrics([r(steps=13)])["stop_rule_never_exceeded"] is False


def test_checkpoint_timeouts_counted():
    assert extra_metrics([r(stop="checkpoint_timeout"), r()])["checkpoint_timeouts"] == 1


def test_tool_counts_per_task_ignore_synthetic_and_skipped():
    a = r(tools=["read_job_posting", "find_jobs", "submit_application"])
    a["trajectory"].append({"tool": "submit_application", "synthetic": True})
    m = extra_metrics([a, {"skipped": True, "passed": True}])
    assert m["firecrawl_reads_per_task"] == 1.0
    assert m["browser_use_runs_per_task"] == 2.0
