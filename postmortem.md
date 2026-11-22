# Postmortem: CV Tailoring Agent

What went wrong, why, and what we learned. Built from `problems.md` (25 entries, 2026-11-14 to 2026-11-21).
Each item names the `problems.md` entry it comes from and the test that now guards it.

## Summary

Most problems were found early, in the first week, while reading our own code. They fell into five groups:
errors that crashed the agent, untrusted text reaching the model, the real model never getting its task,
test and tooling hygiene, and a late change of provider. The live runs and the instructor's answers were
the main things we could not finish. They are listed under "Still open" and are not presented as done.

## 1. Errors that crashed the run instead of being reported

| What went wrong | Why | Fix and guard test |
|---|---|---|
| Unknown tool, bad `kind` in `save_tailored_cv`, a failed submit gate and a malformed model reply all raised `ValueError` and ended the run | We used `raise` where the design said "return a structured error" | Every path returns `make_error(...)`; a bad reply counts as a step and `max_steps` ends the run. `test_tool_registry.py`, `test_errors.py` |
| After a failed `read_job_posting`, `job` held the error dict | State was updated after every call, success or not | State is only updated when `is_error(result)` is false. `test_failed_read_does_not_set_job` |
| `FAULT_MODE=unknown` returned a code that was not in `ERROR_CODES`, so it was stored as the job | `is_error` checked membership in the list | `is_error` now checks for any string under `error`. `test_is_error_true_for_unknown_code` |

**Lesson:** decide the error contract before writing tools, and test the failure path as often as the success path.
Four of the first seven problems were the same mistake in four places.

## 2. Untrusted text

- A posting containing `</tool_result>` closed our untrusted wrapper early, so injected text could sit outside the
  untrusted zone. We fixed it by escaping `<`, `>` and `&` after serialising. `test_untrusted.py`
- Person D's review (week 1) found that `read_job_posting` did no HTML, hidden-text or zero-width stripping and had no
  length limit. This became the messy-pages work (`posting_cleaner.py`, the `tests/fixtures/messy_pages/` cases,
  scenarios s27 to s30).

**Lesson:** the wrapper was the first defence we attacked ourselves, and it had a hole. Test defences with hostile input,
not only normal input.

## 3. The real model never received a task

Three bugs hid behind the fake model, which ignores its input and replays a script:

- `_convert_messages` dropped `user` messages, so the model got an empty list.
- `--job-url` was parsed and never used.
- `max_tokens=1024` cut the CV and cover letter off inside the JSON reply (now 4096).

A fourth, smaller one: the fake walkthrough submitted `job_001_cv.txt` while the tool wrote `cv_job_001.md`.

**Lesson:** a fake that always succeeds proves little about the real path. These were found by reading code, before any
live run. Without that review they would have shown up on the first paid call.

## 4. Test and tooling hygiene

- Tests wrote real `.jsonl` files into `logs/`. A function-scoped fixture now points `CV_AGENT_LOG_DIR` at `tmp_path`.
- `.env` was never loaded, so the README instruction did nothing. `_load_dotenv()` fixes that and never overrides
  variables that are already set.
- Token counts in the log were always 0 and there was no cost field. The loop now reads `usage`, and the stop event
  carries totals.
- `docs/sandbox.md` listed `job_003` at 0.00 even though "Java" is a substring of "JavaScript". We verified scores
  instead of trusting the table, and the `match_skills` upgrade (word boundaries, French aliases) corrected them.

**Lesson:** documentation that states an expected result is itself something to test.

## 5. Provider change and quota handling

The team only had an OpenAI key, but the design used the Anthropic API. We replaced the adapter, the dependency and
every doc that mentioned it. A related failure: with no credits, a 429 was retried as if it were a rate limit and then
ended in a raw traceback. Quota errors now stop at once with a clear message and exit code 2. `test_model.py`,
`test_main.py`.

**Lesson:** confirm the provider and the key before building the adapter. Treat "no credit" differently from "slow down".

## 6. Metrics that can mislead

- `stop_reason == "done"` does not mean the application was submitted. The runner now requires a successful
  `submit_application` result as well.
- `s08_portal_fail_once` passes but records `step_accuracy: 0.0`, `tool_call_precision: 0.0` and 7 wasted steps,
  because the expected-step matching does not allow for the retry. Mean step accuracy is 0.9697 and mean wasted steps is
  0.2121 across the suite, so those two numbers are slightly pessimistic for that scenario. We have documented this
  and not changed the metric.

## Still open (not done)

1. **Live runs.** The 3x live injection runs (Inj-b) and the 3x live subset (C8) did not run: no `OPENAI_API_KEY` in the
   evaluation environment and no confirmed budget. All reported results are replay or fake runs with $0.00 recorded
   spend. The report must say so.
2. **Instructor approval.** As of the 2026-11-20 entry the approval email was NOT YET SENT and questions 1 to 5 were
   unanswered, including whether automated access to the three real sites needs authorisation. Until it is answered the
   fallback is our own sandbox and saved snapshots.
3. **Stale injection results.** `eval/results/inj_fake/` still holds names from an older numbering (for example
   `i09_company_name_injection`, `i11_hidden_text_injection`, and no `i12`). The current results are
   `inj_run1` to `inj_run3`. The old folder should be removed or relabelled so the report does not cite it.
4. **Deployment.** Not started at the time of writing (needs a host account and the model key).

## What we would do differently

1. Write the error contract and the untrusted-text defences before the tools.
2. Run one live call early, even a tiny one, to prove the real path before building 33 scenarios on the fake one.
3. Send the instructor message in week 1. Several decisions (budget, site access, Pages) waited on it.
4. Keep one results folder per run and delete the old ones, so every number in the report traces to a single run.
