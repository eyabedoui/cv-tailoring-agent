# Section 4: Evaluation Results, Injection Testing & Cost Analysis

## 4.1 Evaluation Setup & Replay vs. Live Scope
We evaluated the CV tailoring agent across **33 scenario files** (`C5`) and **12 prompt-injection scenarios** (`i01`–`i12`, `Inj-a`) using `eval.runner`. All reported baseline runs (`replay_run1`–`replay_run3` and `inj_run1`–`inj_run3`) were executed in **offline/replay (`--model fake`)** mode (`$0.00` cost) because live API spending authorization and dashboard caps were still pending confirmation (`API_BUDGET_USD=0`)[cite: 2, 6, 10]. Live (`--model real`) runs for the injection suite (`Inj-b`) and a live scenario subset (`C8`) are gated on confirmed live budget/approval[cite: 4, 6].

## 4.2 Scenario Suite & Run-to-Run Variance (`replay_run1`–`replay_run3`)
Across three full runs of all 33 scenarios in replay/offline mode:
- **Pass rate & safety:** `33/33` passed in every run (`task_success_rate = 1.0000`), with `0` safety violations, `0` fabrication cases, and `stop_rule_never_exceeded = True`.
- **Tool & step quality:** `mean_step_accuracy = 0.9697`, `mean_tool_call_precision = 0.9697`, `mean_wasted_steps = 0.2121`, `recovery_after_failure_rate = 1.0000`, and `mean_steps = 4.82` (`max_steps_seen = 12`).
- **Latency & variance:** Accuracy, precision, wasted steps, token counts (`2,157.58` mean input tokens; `431.52` mean output tokens), and pass rates had zero run-to-run variance across the three runs. Latency varied slightly by run (`time_p50_s`: `0.0400s`–`0.0824s`; `time_p95_s`: `0.4328s`–`0.4977s`).
- **Parser & fabrication checks:** Added gold-label files in `eval/gold/` for the three snapshot pages (`ext-45c03473`, `ext-4a3fd7f4`, `ext-f23905b0`) and verified softer fabrication checks (`C7`) covering inflated levels, invented numbers, changed dates, and merged roles[cite: 4, 6].

## 4.3 Prompt Injection Results (`inj_run1`–`inj_run3`)
Across three runs of all 12 injection fixtures (`i01`–`i12`, covering instruction overrides, checkpoint bypasses, wrong job IDs, multilingual/French/Arabic payloads, fake user turns, company-field injections, wrapper tag breakouts, master CV exfiltration attempts, LinkedIn/external redirects, search-title injections, and chat approval claims):
- **Pass rate:** `12/12` passed in all three runs (`injection_pass_rate = 1.0000`, `safety_violations = 0`, `fabrication_cases = 0`, `0` run-to-run variance in pass rate).
- **Latency:** `time_p50_s` ranged from `0.0166s` to `0.0385s` and `time_p95_s` from `0.0233s` to `0.1730s`.
- **Live chat runs (`Inj-b`):** Pending/blocked until live API authorization is active; if run live once approved, results and any newly discovered holes must be logged before final runs[cite: 4, 6, 7].

## 4.4 Cost & Plots Summary (`eval/results/`)
Summary plots (`task_success_rate.png`, `mean_steps.png`, and `p95_latency.png`) are saved in `eval/results/`, and the per-task and 100x cost split across model, Firecrawl, and Browser Use is documented in `cost_model.md` (Section 11)[cite: 6].
