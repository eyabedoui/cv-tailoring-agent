# Problems Log

Each entry: date · symptom · cause · fix · test name.

---

## 2026-11-14 · execute_tool raised ValueError on unknown tool
- **Symptom**: Calling `execute_tool("unknown_tool", {})` raised `ValueError`
  instead of returning a structured error.
- **Cause**: The registry used `raise ValueError(...)` for unknown tools.
- **Fix**: Changed to `return make_error(UNKNOWN_TOOL, ...)` (error contract).
- **Test**: `test_tool_registry.py::test_unknown_tool_is_rejected` updated —
  now checks `result["error"] == "UNKNOWN_TOOL"` instead of `pytest.raises`.

## 2026-11-14 · save_tailored_cv raised ValueError on bad kind
- **Symptom**: `save_tailored_cv(kind="invalid")` raised `ValueError`.
- **Cause**: Stubs used `raise ValueError(...)` instead of returning an error.
- **Fix**: Returns `make_error(INVALID_ARGUMENTS, ...)` now.
- **Test**: `test_tool_registry.py::test_save_tailored_cv_rejects_invalid_kind`
  updated — checks error dict instead of `pytest.raises`.

## 2026-11-14 · loop stored state from failed tool results
- **Symptom**: If `read_job_posting` failed, `job` was set to the error dict;
  if `save_tailored_cv` failed, `tailored_cv` was still set from arguments.
- **Cause**: State was updated unconditionally after every tool call.
- **Fix**: `is_error(result)` guard — state only updated from successful results.
- **Test**: `test_errors.py::test_failed_read_does_not_set_job`,
  `test_errors.py::test_failed_save_does_not_set_tailored_cv`.

## 2026-11-14 · submit gate raised ValueError, crashing the loop
- **Symptom**: Missing prerequisites or mismatched job_id caused `ValueError`
  in the submit gate, crashing the run instead of continuing.
- **Cause**: Gate used `raise ValueError(...)`.
- **Fix**: Gate returns `make_error(INVALID_ARGUMENTS, ...)` and continues.
- **Test**: `test_errors.py::test_submit_mismatched_job_id_does_not_crash`.

## 2026-11-14 · malformed model response raised ValueError
- **Symptom**: Non-dict or unsupported-type model responses raised `ValueError`,
  terminating the run with an exception instead of stopping by max_steps.
- **Cause**: Loop used `raise ValueError(...)` for bad responses.
- **Fix**: Bad responses count as a step and return `make_error(BAD_RESPONSE)`
  to the model; `should_stop` eventually fires `max_steps`.
- **Test**: `test_errors.py::test_malformed_model_output_ends_by_max_steps`,
  `test_errors.py::test_unsupported_response_type_ends_by_max_steps`.

## 2026-11-14 · `<` in tool result could escape untrusted wrapper
- **Symptom**: A job posting containing `</tool_result>` closed the wrapper tag
  early, allowing injected content to appear outside the untrusted zone.
- **Cause**: `json.dumps` output was embedded in the tag without escaping.
- **Fix**: `wrap_untrusted()` replaces `<`→`<`, `>`→`>`,
  `&`→`&` after serialisation; `json.loads` decodes them back.
- **Test**: `test_untrusted.py::test_wrap_produces_exactly_one_opening_and_closing_tag`,
  `test_untrusted.py::test_original_text_is_recoverable`.

## 2026-11-14 · tokens_in/tokens_out always 0; no cost or timing in log
- **Symptom**: All token counts in the log were 0; no cost field; stop event
  had no run-total timing.
- **Cause**: Loop never read `usage` from model responses; logger never computed
  cost; `log_stop` had no totals parameters.
- **Fix**: Loop reads `response.get("usage", {})` and passes tokens to
  `log_step`; logger accumulates totals; `log_stop` gains
  `total_tokens_in/out`, `total_cost_usd`, `total_duration_ms`.
- **Test**: `test_logger.py::test_usage_flows_through_fake_model`,
  `test_logger.py::test_stop_event_has_total_fields`.

---

## Handoff note for Person B

**Built in this pass (Person A, 2026-11-14):**

### New files
| File | Purpose |
|------|---------|
| `agent/errors.py` | Error contract: `make_error`, `is_error`, `ERROR_CODES` |
| `agent/untrusted.py` | `wrap_untrusted(result)` — escapes `<>/&` in JSON |
| `agent/model.py` | `AnthropicModel` — real Anthropic API adapter |
| `agent/__main__.py` | `python -m agent` entry point; `--model fake\|anthropic` |
| `docs/decisions.md` | All design decisions documented |
| `requirements.txt` | `anthropic`, `pytest` |
| `.env.example` | `ANTHROPIC_API_KEY=`, `CV_AGENT_MODEL=` |
| `problems.md` | This file |

### Modified files
| File | What changed |
|------|-------------|
| `agent/config.py` | Added `CANDIDATE_ID`, `SANDBOX_DIR`, `ALLOWED_URL_PREFIX`, `CHECKPOINT_TIMEOUT_SECONDS`, price constants |
| `agent/loop.py` | Error contract, state guard, submit gate fix, malformed-response handling, usage tokens, untrusted wrapper |
| `agent/logger.py` | `cost_usd` per step, totals in stop event, `timed_out` in checkpoint event |
| `agent/checkpoint.py` | `timeout_seconds` param, daemon-thread input, `timed_out` flag |
| `agent/stop_rule.py` | `checkpoint_timeout` stop reason |
| `agent/prompts.py` | `JSON_PROTOCOL_PROMPT` constant |
| `agent/tools/stubs.py` | `save_tailored_cv` returns `make_error` on bad kind |
| `agent/tools/registry.py` | `execute_tool` returns `make_error` instead of raising |
| `docs/log_format.md` | New fields, fixed duplicate section 3, `checkpoint_timeout` stop reason |
| `.gitignore` | Added `.env` |
| `README.md` | Full skeleton |

### How to run
```bash
pip install -r requirements.txt
python -m agent --model fake --auto-approve        # no API key needed
python -m agent --job-url mock://jobs/job_001      # real model (needs .env)
python -m pytest -q                                # 93 tests, all green
```

### Error contract
Errors are `{"error": CODE, "message": "plain text", "retryable": bool}`.
`is_error(result)` checks membership in `ERROR_CODES`.
State (job, master_cv, tailored_cv, cover_letter, match_score) is NEVER updated
from an error result — the model receives the error and can retry or give up.

### Untrusted wrapper
`agent/untrusted.py::wrap_untrusted(result)` — use this for all tool results.
It escapes `<`, `>`, `&` with JSON unicode escapes so injected tags cannot
escape the `<tool_result untrusted="true">` boundary.

### New config constants (agent/config.py)
- `CANDIDATE_ID = "candidate_001"`
- `SANDBOX_DIR = "sandbox"`
- `ALLOWED_URL_PREFIX = "mock://"`
- `CHECKPOINT_TIMEOUT_SECONDS = 120`
- `PRICE_PER_MTOK_INPUT = 0.0` — fill from provider price list
- `PRICE_PER_MTOK_OUTPUT = 0.0` — fill from provider price list

### Choices that differ from the prompt
- `execute_tool` in `registry.py` now returns `make_error` instead of raising.
  The prompt said "exceptions raised by tools become make_error results in
  loop.py", but catching in the registry is simpler and keeps the loop clean.
- The fake-model walkthrough uses `arguments` exactly matching the stub tool
  signatures (not the job_url passed on the CLI) because the stubs are fixed.
  Person B's real tools will use the actual `--job-url` value.
- `invalid_response` is returned (not raising) from `_parse_response` to keep
  the loop's bad-response path consistent with the error contract.

---

## Handoff note for Person C

**Built in this pass (Person B, 2026-11-14):**

### New files

| File | Purpose |
|------|---------|
| `agent/tools/schemas.py` | Pydantic v2 input + output models for all 6 tools; `TOOL_SCHEMA_MAP` |
| `agent/tools/reads.py` | Real read tools: `read_job_posting`, `read_master_cv`, `match_skills`, `check_format` |
| `agent/tools/writes.py` | Real write tools: `save_tailored_cv` (atomic rename), `submit_application` (PATH_NOT_ALLOWED + DUPLICATE_SUBMISSION) |
| `sandbox/__init__.py` | Makes `sandbox` a Python package |
| `sandbox/portal.py` | `Portal` class — file-system-backed job postings + application state |
| `sandbox/seed.py` | 25 deterministic fictional job postings (`job_001`–`job_025`) |
| `sandbox/faults.py` | `check_fault()` — FAULT_MODE fault injection for read and submit |
| `sandbox/manage.py` | `setup`, `seed`, `reset`, `run` sandbox management commands |
| `sandbox/__main__.py` | `python -m sandbox <command>` entry point |
| `sandbox/master_cv.md` | Fictional candidate CV (candidate_001, Alex Jordan) |
| `sandbox/missing_skills.md` | Skills the candidate genuinely does not have (fabrication guard) |
| `docs/sandbox.md` | Table of all 25 postings with expected match scores |
| `Makefile` | `install`, `test`, `sandbox-*`, `run-fake`, `run` targets |
| `tests/conftest.py` | Session fixture — seeds `sandbox/postings/` before tests run |
| `tests/test_schemas.py` | 32 tests: Pydantic input/output models + registry validation layer |
| `tests/test_portal.py` | 20 tests: Portal operations + seed data consistency |
| `tests/test_write_tools.py` | 19 tests: atomic save, PATH_NOT_ALLOWED, DUPLICATE_SUBMISSION |
| `tests/test_read_tools.py` | 33 tests: all four read tools, alias matching, error paths, 0.75 score |
| `tests/test_fault_modes.py` | 21 tests: all 6 FAULT_MODE values on read and submit |

### Modified files

| File | What changed |
|------|-------------|
| `agent/tools/registry.py` | Pydantic input/output validation; `input_schema` in `TOOL_SCHEMAS`; real tools replacing stubs |
| `requirements.txt` | Added `pydantic>=2.0` |
| `.gitignore` | Excludes `sandbox/postings/`, `sandbox/output/`, `sandbox/state/` |

### How to run

```
pip install -r requirements.txt
python -m sandbox reset
python -m sandbox seed
python -m agent --model fake --auto-approve
python -m pytest -q                       # 228 tests, all green
```

### Design decisions

- **Portal injection** (`_portal=None`): read and write tool functions accept
  an optional `_portal` keyword argument so tests can inject a `tmp_path`-backed
  portal without touching the real `sandbox/` directory. When called through
  `execute_tool` the argument is absent and the module-level default is used.
- **Alias matching**: `match_skills` uses a small hardcoded alias table
  (`_SKILL_ALIASES` in `reads.py`) for common variations (e.g. "unit testing" →
  "pytest"). Short aliases like "ml" were intentionally excluded because they are
  substrings of unrelated words ("html").
- **Atomic writes**: both `save_tailored_cv` and `portal.record_application`
  write to a `.tmp` file first, then `os.replace()` to avoid partial writes.
- **PATH_NOT_ALLOWED**: `submit_application` rejects absolute paths and paths
  containing `..` components. On Windows `Path.is_absolute()` does not detect
  Unix-style `/etc/passwd`, so the check also tests `path_str.startswith("/")`.
- **FAULT_MODE** only fires in `read_job_posting` and `submit_application` (the
  two portal-touching operations). `reject_duplicate` only fires for `context="submit"`.
- `sandbox/manage.py reset()` deletes files inside `output/` and `state/` without
  removing the directories themselves — required on Windows/OneDrive where
  `shutil.rmtree` on a sync-locked directory raises `PermissionError`.
- **conftest.py** seeds `sandbox/postings/` once per test session so registry
  integration tests that call `read_job_posting` through `execute_tool` find real
  posting files without needing a manual `python -m sandbox seed` before testing.

### What Person C still needs to do

Week 2 (not in this pass):
- HTML stripping for real job postings
- Injection/adversarial posting scenarios (Person C's fabrication checker)
- Messy-posting handling
- Eval scenarios
- Final README updates

---

## Handoff note for Person D (from Person C, week 1)

### Built
| File | Purpose |
|------|---------|
| `eval/schema.json`, `eval/METRICS.md` | Scenario format, metric formulas, result format |
| `eval/runner.py` | `python -m eval.runner --folder <dir> --model fake\|real` |
| `eval/fabrication.py` | `check_fabrication(master, tailored)` v1: skills, employers, degrees |
| `eval/scenarios/` | 15 scenarios (s01 to s15). s12 and s13 are `fake_only` |
| `tests/test_runner.py`, `tests/test_fabrication.py` | Runner and checker tests |

### For D: injection cases use the same runner
Put JSON files in `eval/injection/` with the same schema. Use `posting` (inline, written for one run
only) with ids job_901 to job_912, `forbidden_calls`, `forbidden_text`, and `decisions`.
Run: `python -m eval.runner --folder eval/injection --model real --run-name inj1`.
A rejected submit is not logged as a tool_call; the runner turns that human_checkpoint event
into a synthetic submit step.

### Findings for A and B (found while reading code, not yet fixed)
- OPEN (owner A) `agent/model.py::_convert_messages` skips messages with role `user`, and
  `python -m agent` calls `agent.run()` with no initial message. The real model gets no task and
  possibly an empty message list. Fix: treat `user` like `tool` (api_role `user`) and pass a task
  message from `--job-url` in `__main__.py`.
  FIXED (A9)
- OPEN (owner A) `--job-url` is parsed in `__main__.py` but never used.
  FIXED (A9)
- OPEN (owner A) `FAULT_MODE=unknown` returns an error dict with an unknown code, so `is_error()` is
  False and the loop stores it as `job` (state is updated from an error). Add the code to
  ERROR_CODES or make `is_error` check for the `error` key.
  FIXED (A9)
- NOTE `stop_reason == "done"` does not mean submitted. Any final answer sets done. The runner
  judges success from the stop reason AND a successful submit_application result.
- NOTE Tests write real log files into `logs/`. `logs/` is in .gitignore. If they are already
  tracked, run `git rm -r --cached logs`.
  FIXED (A9)
- NOTE `docs/sandbox.md` says matching is substring-based but lists job_003 as 0.00 even though
  "Java" is a substring of "JavaScript". Verify scores before trusting the no_match scenarios.

---

## Review notes from Person D (week 1, 2026-11-15)

- OPEN (owner B, B7) `read_job_posting` returns title, company and text with no HTML, hidden-text or zero-width stripping and no length limit. Needed for injection cases 6 and 8.
- OPEN (owner A) Real-model injection runs are blocked by the missing task message in `agent/model.py` (see Person C's finding above).
  FIXED (A9)
- NOTE `agent/untrusted.py` reviewed: the wrapper escapes `<`, `>` and `&` and no hole was found.

---

## 2026-11-19 · `_convert_messages` dropped user messages; empty message list sent to API
- **Symptom**: Real-model runs sent no task to the model; `user` messages from `initial_messages` were silently discarded, and if only an `assistant` message preceded the first API call the list could start with a non-user role, violating the Anthropic API contract.
- **Cause**: `_convert_messages` had no branch for `role == "user"` and fell through to `continue`.
- **Fix**: Added `user` to the pass-through branch (api_role `"user"`). After conversion, if the list is empty or starts with `"assistant"`, prepend `{"role": "user", "content": "Start the task."}`.
- **Test**: `test_model.py::test_convert_user_message_is_kept`, `test_convert_user_message_is_first`, `test_convert_prepends_start_task_when_first_is_assistant`, `test_convert_prepends_start_task_for_empty_input`, `test_convert_prepends_start_task_for_system_only`.

## 2026-11-19 · `--job-url` parsed but never used; real model received no task
- **Symptom**: Running `python -m agent --job-url mock://jobs/job_001` passed no initial message to the loop, so the real model had nothing to act on.
- **Cause**: `agent/__main__.py` called `agent.run()` with no `initial_messages` argument despite having the URL available.
- **Fix**: Build a user message from `--job-url` and pass it via `initial_messages=[...]`. Added `--request TEXT` flag to override the generated message.
- **Test**: `test_main.py::test_no_request_flag_uses_job_url`, `test_request_flag_replaces_generated_message`, `test_request_flag_ignores_job_url`.

## 2026-11-19 · `max_tokens=1024` truncated CV and cover letter content in JSON replies
- **Symptom**: Real-model runs returned truncated output; CV and cover letter content was cut off inside the JSON reply.
- **Cause**: `AnthropicModel.call_model` hard-coded `max_tokens=1024`.
- **Fix**: Added `MODEL_MAX_TOKENS = 4096` to `agent/config.py`; `call_model` now uses `MODEL_MAX_TOKENS`.
- **Test**: `test_model.py::test_max_tokens_equals_model_max_tokens`.

## 2026-11-19 · Wrong file paths in `FAKE_WALKTHROUGH_RESPONSES` submit step
- **Symptom**: The fake walkthrough's `submit_application` step referenced `job_001_cv.txt` and `job_001_cover_letter.txt`, but `save_tailored_cv` actually writes `cv_job_001.md` and `cover_letter_job_001.md`.
- **Cause**: Stale placeholder paths were copy-pasted from an earlier design; filename convention changed in Person B's real write tools.
- **Fix**: Updated `FAKE_WALKTHROUGH_RESPONSES` to use `sandbox/output/cv_job_001.md` and `sandbox/output/cover_letter_job_001.md`.
- **Test**: `test_main.py::test_fake_walkthrough_cv_path_matches_save_tailored_cv`, `test_fake_walkthrough_cover_letter_path_matches_save_tailored_cv`.

## 2026-11-19 · Tests wrote real log files into `logs/`
- **Symptom**: Running the test suite created `.jsonl` files in `logs/` in the repo working tree.
- **Cause**: `AgentLogger` defaulted to `log_dir="logs"` and tests that constructed `AgentLoop` without an explicit logger inherited this default.
- **Fix**: `AgentLogger.__init__` checks the `CV_AGENT_LOG_DIR` environment variable before falling back to `"logs/"`. A new function-scoped `autouse` fixture in `tests/conftest.py` sets `CV_AGENT_LOG_DIR` to the pytest `tmp_path` for every test.
- **Test**: All existing logger and runner tests continue to pass; logs no longer appear in `logs/` after `pytest`.

## 2026-11-19 · `.env` file never loaded; `ANTHROPIC_API_KEY` had to be set manually
- **Symptom**: README said "cp .env.example .env" but nothing read `.env`, so `ANTHROPIC_API_KEY` was always missing even when the file existed.
- **Cause**: No `.env` loading code in the entry point.
- **Fix**: Added `_load_dotenv()` in `agent/__main__.py`: reads simple `KEY=VALUE` lines (skips blanks and `#` comments, strips quotes), sets missing env vars with `os.environ.setdefault`. Never overrides existing variables.
- **Test**: `test_main.py::test_load_dotenv_sets_missing_variable`, `test_load_dotenv_does_not_override_existing`, `test_load_dotenv_ignores_blank_lines_and_comments`, `test_load_dotenv_strips_quotes`, `test_load_dotenv_no_file_does_nothing`.

## 2026-11-19 · Unknown `FAULT_MODE` error code stored as job state
- **Symptom**: `FAULT_MODE=unknown` returned `{"error": "FAULT_INJECTED", ...}`; because `"FAULT_INJECTED"` is not in `ERROR_CODES`, `is_error()` returned `False` and the loop updated `job` with the error dict.
- **Cause**: `is_error()` checked `result["error"] in ERROR_CODES` rather than testing for the presence of a string `"error"` key.
- **Fix**: `is_error()` now returns `True` for any `dict` where `"error"` maps to a `str`, regardless of whether the code is in `ERROR_CODES`. `ERROR_CODES` remains the canonical list of known codes.
- **Test**: `test_errors.py::test_is_error_true_for_unknown_code`, `test_errors.py::test_unknown_fault_code_does_not_set_job`; updated comment in `test_fault_modes.py::test_unknown_fault_returns_non_standard_error_code`.
