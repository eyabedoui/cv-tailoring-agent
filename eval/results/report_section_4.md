# 4. Evaluation, Security Testing, and Cost Model

## 4.1 Evaluation Setup and Modes
We evaluated the CV Tailoring Agent across 33 evaluation scenarios (`s01`–`s33`) covering normal job matching, multi-turn chats, revision limits, messy pages, site/tool blocks, timeouts, and fault recovery (`fail_once`, portal/Firecrawl/Browser Use failures), plus 12 prompt-injection scenarios (`i01`–`i12`). Three full evaluation runs (`replay_run1..3`) and three injection runs (`inj_run1..3`) were recorded, alongside 880 passing unit/integration tests and plots (`task_success_rate.png`, `mean_steps.png`, `p95_latency.png`) in `eval/results/`.

**Mode Disclosure (Replay/Local vs. Live):** All recorded multi-run outputs in `replay_run1..3` and `inj_run1..3` were executed locally in replay/fake mode with `$0.00` recorded API cost (`mean_cost_usd = 0.0`) rather than live paid API runs. In accordance with project fallbacks when live keys/budgets are not active during evaluation, replay/local runs serve as the primary recorded benchmark here.

## 4.2 Task Performance, Reliability, and Run-to-Run Variance
Across all three 33-scenario runs (`replay_run1..3`):

* **Task Success & Recovery:** `task_success_rate = 1.0000` (`33/33` passed per run, `stdev = 0.0000`) and `recovery_after_failure_rate = 1.0` (`stdev = 0.0000`).
* **Step & Tool Metrics:** `mean_steps = 4.82` (`stdev = 0.0000`), `max_steps_seen = 12`, `mean_step_accuracy = 0.9697` (`stdev = 0.0000`), `mean_tool_call_precision = 0.9697` (`stdev = 0.0000`), and `mean_wasted_steps = 0.2121` (`stdev = 0.0000`). Stop rules were never exceeded (`stop_rule_never_exceeded = true`), with `1` expected checkpoint timeout (`checkpoint_timeouts = 1`).
* **Known Metric Caveat (`s08_portal_fail_once`):** In `s08_portal_fail_once`, the agent recovered and passed (`passed = true`, `submitted = true`), but step scoring recorded `step_accuracy = 0.0`, `tool_call_precision = 0.0`, and `wasted_steps = 7` due to expected-step matching on retry; this single scenario accounts for the `0.9697` accuracy and `0.2121` wasted-step averages.
* **Latency:** Median latency `p50` averaged `0.0592s` (`[0.0824s, 0.0553s, 0.0400s]`, `stdev = 0.0215s`) and `p95` averaged `0.4554s` (`[0.4977s, 0.4358s, 0.4328s]`, `stdev = 0.0366s`).

## 4.3 Prompt Injection and Fabrication Defense

* **Injection Runs (`inj_run1..3`):** Across 3 runs of all 12 injection scenarios (`i01`–`i12`), `injection_pass_rate = 1.0000` (`12/12` passed per run, `stdev = 0.0000`) with `safety_violations = 0` (`stdev = 0.0000`). No unauthorized submissions, off-allowlist navigations, or master-CV leaks occurred. Latency `p50` averaged `0.0254s` (`stdev = 0.0115s`) and `p95` averaged `0.0845s` (`stdev = 0.0785s`).
* **Fabrication & Parser Checks:** `fabrication_cases = 0` across all replay and injection runs. Fabrication checks cover invented skills, employers, and degrees as well as softer fabrications (inflated level terms, invented numbers, changed dates, and merged roles), while `parser_accuracy` evaluates extracted requirements against gold-label JSON files in `eval/gold/`.

## 4.4 Cost Model (1x and 100x Scaling by Service)
From `replay_run1..3` (`n = 33` scenarios/run), per-task resource usage averaged `2,157.58` input tokens (`stdev = 0.0000`), `431.52` output tokens (`stdev = 0.0000`), `0.97` Firecrawl reads (`stdev = 0.0000`), and `0.667` Browser Use runs (`stdev = 0.0000`), with `$0.00` recorded spend in replay.

Let `(P_in, P_out)` denote model prices in USD per 1M input/output tokens, `C_fc` denote Firecrawl cost per read, and `C_bu` denote Browser Use cost per run:

| Component | Per-Task Usage (`1x`) | `1x` Cost Formula (Replay Recorded) | `100x` Usage | `100x` Cost Formula (Replay Recorded) |
| :--- | :--- | :--- | :--- | :--- |
| **Model (OpenAI)** | `2,157.58` in / `431.52` out tokens | `(2157.58 * P_in + 431.52 * P_out) / 1e6` (`$0.00`) | `215,758` in / `43,152` out tokens | `100 * (2157.58 * P_in + 431.52 * P_out) / 1e6` (`$0.00`) |
| **Firecrawl** | `0.97` reads/task | `0.97 * C_fc` (`$0.00`) | `~97` reads | `97 * C_fc` (`$0.00`) |
| **Browser Use** | `0.667` runs/task | `0.667 * C_bu` (`$0.00`) | `~67` runs | `66.7 * C_bu` (`$0.00`) |

Cost controls—including step/session caps, single-scrape-per-posting reads, replay-first evaluation, and provider/budget caps—keep evaluation predictable and within proposed budget limits (`$3.00` OpenAI, free-tier Firecrawl, `$2.00` Browser Use equivalent, `$5.00` total proposed cap) once live pricing and dashboard limits are activated.
