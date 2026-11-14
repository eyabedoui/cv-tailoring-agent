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
