"""A5: Verify safe alternative-site fallback in an agent scenario."""

from pathlib import Path

from eval import runner


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_FILE = (
    ROOT / "eval" / "scenarios" / "s17_site_not_allowed.json"
)


def test_site_not_allowed_offers_safe_alternative(tmp_path):
    scenario = runner.load_scenarios(SCENARIO_FILE.parent)
    scenario = next(
        s for s in scenario
        if s["id"] == "s17_site_not_allowed"
    )

    result = runner.run_scenario(
        scenario,
        "fake",
        log_dir=tmp_path,
    )

    assert result["passed"], result["mismatches"]
    assert result["stop_reason"] == "done"
    assert result["submitted"] is False

    # The scenario's response must offer an allowed alternative.
    final_response = scenario["fake_script"][-1]["final"].lower()

    assert "linkedin" in final_response
    assert "not in the list of allowed" in final_response

    assert any(
        site in final_response
        for site in ("tanitjobs", "keejob", "weworkremotely")
    )

    # The candidate must be asked before searching another site.
    assert "would you like" in final_response

    # Only the unauthorized search is requested in the script.
    tool_calls = [
        step for step in scenario["fake_script"]
        if "tool" in step
    ]

    assert len(tool_calls) == 1
    assert tool_calls[0]["tool"] == "find_jobs"
    assert tool_calls[0]["args"]["site"] == "linkedin"