# A6 — Stop Rules and Reliability Evidence

## Objective

Verify that the CV Tailoring Agent terminates safely under normal completion, repeated failures, excessive tool calls, and human approval interruptions.

## Stop-condition evidence

| Scenario                     | Expected behavior                    | Test evidence                    |
| ---------------------------- | ------------------------------------ | -------------------------------- |
| Never-stopping model         | Stop at `MAX_STEPS` with `max_steps` | 3 tests passed                   |
| Always-failing tool          | Stop with `repeated_call`            | 2 tests passed                   |
| Three identical calls        | Stop with `repeated_call`            | Existing unit tests passed       |
| Low skill match              | Stop with `no_match`                 | Existing unit tests passed       |
| Human rejection              | Stop with `user_rejected`            | Existing unit tests passed       |
| Checkpoint timeout           | Stop with `checkpoint_timeout`       | Existing tests passed            |
| Successful completion        | Stop with `done`                     | 2 completion tests passed        |
| Per-turn step cap            | Stop with `max_steps`                | Existing agent-loop tests passed |
| Per-session step cap         | Stop with `session_limit`            | Existing session tests passed    |
| Browser Use search limit     | Pass `max_steps=20`, `timeout=120`   | Static configuration test passed |
| Browser Use submission limit | Pass `max_steps=10`, `timeout=60`    | Static configuration test passed |

## Test commands and results

**Stop-rule and completion tests**

`python -m pytest tests/test_stop_rule_unit.py tests/test_a6_completion.py -q`

Result: **10 passed in 0.12s**

**Browser Use configuration tests**

`python -m pytest tests/test_a6_browser_limits.py -q`

Result: **2 passed in 0.09s**

**Always-failing-tool tests**

`python -m pytest tests/test_a6_failing_tool.py -q`

Result: **2 passed in 0.37s**

\*\*
