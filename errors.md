# Error taxonomy — CV Tailoring Agent

## Planning table (Week 1)

One row per error class.  The "Test ids" column is the authoritative reference; see the
implementation table below for exact codes and real test names.

| Class | What the agent does | Planned test and scenario | Test ids | Owner |
|---|---|---|---|---|
| Tool down | Retries a transient error up to 2 times, then stops with a clear message | FAULT_MODE=down (B6), A5 test | test_down_returns_portal_down_on_read | B6, A5 |
| Bad arguments | Tool returns INVALID_ARGUMENTS, the model corrects the call, no retry loop | Schema rejection test (B2), C5 scenario | test_invalid_job_id_returns_invalid_arguments | B2, C5 |
| Empty result | Treats an empty or missing posting as a stop, not a guess | Empty posting test (B7), C5 scenario | test_read_job_posting_empty_text_returns_empty_posting | B7, C5 |
| Wrong tool | Unknown tool or wrong order returns an error, submit is refused before CV and cover letter exist | Loop test, C5 scenario | test_unknown_tool_is_rejected | A5, C5 |
| Loop | Stops on the same call three times (repeated_call) or at 12 steps | A6 tests | test_agent_loop_stops_after_three_identical_calls | A6 |
| Timeout | Tool timeout is retried, checkpoint timeout counts as rejection | FAULT_MODE=timeout (B6), checkpoint timeout test (A6) | test_timeout_returns_timeout_on_read | B6, A6 |
| User changes mind | Reject stops with no submit, change request allows at most 2 revisions | A7 tests, C5 scenarios | test_s19_user_changes_mind | A7, C5 |
| Site not allowed | find_jobs/read_job_posting return SITE_NOT_ALLOWED when site or URL is not in the allowlist; agent tells candidate and asks what to do | test_find_jobs.py, test_sites.py (A13) | test_find_jobs_unknown_site_returns_site_not_allowed | A13 |
| Site blocked | find_jobs returns SITE_BLOCKED (captcha, login wall, FAULT_MODE=blocked); agent tells candidate plainly, does not retry same call | test_find_jobs.py (A13) | test_blocked_find_jobs_returns_site_blocked | A13 |

---

## Implementation reference (Week 1 D)

All tool errors are returned as `{"error": "<CODE>", "message": "...", "retryable": bool}`.
The model receives the dict as plain text; it never raises a Python exception to the loop.

| Code | retryable | When raised | Real test |
|---|---|---|---|
| `SITE_NOT_ALLOWED` | false | `find_jobs` or `read_job_posting` called with a host not in `allowed_sites.json` (e.g. linkedin.com or any unlisted URL). Never retried. | `test_find_jobs_unknown_site_returns_site_not_allowed` (test_find_jobs.py) |
| `SITE_BLOCKED` | false | `FAULT_MODE=blocked` is set; every read and search call is blocked to test the agent's error-handling path. Never retried. | `test_blocked_find_jobs_returns_site_blocked` (test_fault_modes_web.py) |
| `NOT_FOUND` | false | The job posting URL returned a 404, or the master CV file does not exist on disk. | `test_read_job_posting_not_found` (test_read_tools.py) |
| `EMPTY_POSTING` | false | Firecrawl or the fake client returned an empty markdown string for a valid URL. | `test_read_job_posting_empty_text_returns_empty_posting` (test_read_tools.py) |
| `PORTAL_DOWN` | **true** | The Flask apply site is unreachable, the Firecrawl service threw a connection error, or `FAULT_MODE=down` is set. | `test_down_returns_portal_down_on_read` (test_fault_modes.py) |
| `TIMEOUT` | **true** | A network request exceeded its timeout, or `FAULT_MODE=timeout` is set. | `test_timeout_returns_timeout_on_read` (test_fault_modes.py) |
| `BAD_RESPONSE` | false | The server replied with an unexpected status code or the browser submit result could not be reconciled with the portal state. | `test_bad_response_on_read` (test_fault_modes.py) |
| `DUPLICATE_SUBMISSION` | false | The portal already has a record for this `job_id`; a second `submit_application` call is rejected. | `test_reject_duplicate_on_submit` (test_fault_modes.py) |
| `PATH_NOT_ALLOWED` | false | A CV or cover-letter path contains `..` (directory traversal) or is an absolute path. | `test_traversal_in_cv_path_rejected` (test_submit_validation.py) |
| `INVALID_ARGUMENTS` | false | A required tool argument is missing, the wrong type, or violates a schema constraint (e.g. a `job_id` that does not match the allowed pattern). | `test_invalid_job_id_returns_invalid_arguments` (test_submit_validation.py) |
| `UNKNOWN_TOOL` | false | The model called a tool name that is not registered in the agent's tool table. | `test_unknown_tool_is_rejected` (test_tool_registry.py) |

### Blocked-site class

`SITE_NOT_ALLOWED` and `SITE_BLOCKED` are distinct codes with different causes but the same
agent-facing behaviour: **stop, do not retry, tell the user.**

| Code | Trigger | Source file |
|---|---|---|
| `SITE_NOT_ALLOWED` | URL hostname is not in `allowed_sites.json` | `agent/sites.py` |
| `SITE_BLOCKED` | `FAULT_MODE=blocked` environment variable | `sandbox/faults.py` |

Both are non-retryable by design: retrying a blocked or unauthorised site is never correct.
The agent is expected to inform the user and stop (see scenarios s17 and s18 in `eval/scenarios/`).

### Fabrication guard

The fabrication checker (`eval/fabrication.py`) is not an error code but a post-hoc evaluation
gate.  `check_fabrication(master_cv, tailored)` returns a list of invented items; the eval runner
fails any scenario where the list is non-empty.  See `tests/test_fabrication.py` and
`tests/test_fabrication_c.py` for coverage.

---

## Known limits (Week 2)

Source: Person C's Leg 2 handover in problems.md and eval/results/report_section_4.md.

- Test ids in the planning table were checked against tests/ on 2026-11-22.
- The recorded runs (replay_run1 to replay_run3 and inj_run1 to inj_run3) were local replay/fake runs with $0.00 recorded API spend. They do not include a live model. Live runs are blocked on the missing OpenAI API key and the pending budget approval.
- s08_portal_fail_once passes (the agent recovers and submits) but records step_accuracy 0.0, tool_call_precision 0.0 and 7 wasted steps, because expected-step matching does not account for the retry. This one scenario explains the averages of 0.9697 step accuracy and 0.2121 wasted steps. It is a scoring limit, not an agent failure.
- The injection runner looks for forbidden text in tool-call arguments only. A forbidden phrase that appears only in the agent's final chat answer is not detected.
