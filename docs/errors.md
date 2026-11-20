# Error reference — CV Tailoring Agent

All tool errors are returned as `{"error": "<CODE>", "message": "...", "retryable": bool}`.
The model receives the dict as plain text; it never raises a Python exception to the loop.

---

## Error classes

| Code | retryable | When raised | Real test |
|---|---|---|---|
| `SITE_NOT_ALLOWED` | false | `find_jobs` or `read_job_posting` called with a host not in `allowed_sites.json` (e.g. linkedin.com or any unlisted URL). Never retried. | `test_find_jobs_unknown_site_returns_site_not_allowed` (test_find_jobs.py) |
| `SITE_BLOCKED` | false | `FAULT_MODE=blocked` is set; every read and search call is blocked to test the agent's error-handling path. Never retried. | `test_blocked_find_jobs_returns_site_blocked` (test_fault_modes_web.py) |
| `NOT_FOUND` | false | The job posting URL returned a 404, or the master CV file does not exist on disk. | `test_read_job_posting_not_found` (test_find_jobs.py) |
| `EMPTY_POSTING` | false | Firecrawl or the fake client returned an empty markdown string for a valid URL. | `test_read_job_posting_empty_text_returns_empty_posting` (test_find_jobs.py) |
| `PORTAL_DOWN` | **true** | The Flask apply site is unreachable, the Firecrawl service threw a connection error, or `FAULT_MODE=down` is set. | `test_down_returns_portal_down_on_read` (test_fault_modes.py) |
| `TIMEOUT` | **true** | A network request exceeded its timeout, or `FAULT_MODE=timeout` is set. | `test_timeout_returns_timeout_on_read` (test_fault_modes.py) |
| `BAD_RESPONSE` | false | The server replied with an unexpected status code or the browser submit result could not be reconciled with the portal state. | `test_bad_response_on_read` (test_fault_modes.py) |
| `DUPLICATE_SUBMISSION` | false | The portal already has a record for this `job_id`; a second `submit_application` call is rejected. | `test_reject_duplicate_on_submit` (test_write_tools.py) |
| `PATH_NOT_ALLOWED` | false | A CV or cover-letter path contains `..` (directory traversal) or is an absolute path. | `test_traversal_in_cv_path_rejected` (test_submit_validation.py) |
| `INVALID_ARGUMENTS` | false | A required tool argument is missing, the wrong type, or violates a schema constraint (e.g. a `job_id` that does not match the allowed pattern). | `test_invalid_job_id_returns_invalid_arguments` (test_find_jobs.py) |
| `UNKNOWN_TOOL` | false | The model called a tool name that is not registered in the agent's tool table. | `test_unknown_tool_name_returns_error_dict` (test_agent_loop.py) |

---

## Blocked-site class

`SITE_NOT_ALLOWED` and `SITE_BLOCKED` are distinct codes with different causes but the same
agent-facing behaviour: **stop, do not retry, tell the user.**

| Code | Trigger | Source file |
|---|---|---|
| `SITE_NOT_ALLOWED` | URL hostname is not in `allowed_sites.json` | `agent/sites.py` |
| `SITE_BLOCKED` | `FAULT_MODE=blocked` environment variable | `sandbox/faults.py` |

Both are non-retryable by design: retrying a blocked or unauthorised site is never correct.
The agent is expected to inform the user and stop (see scenarios s17 and s18 in `eval/scenarios/`).

---

## Fabrication guard

The fabrication checker (`eval/fabrication.py`) is not an error code but a post-hoc evaluation
gate.  `check_fabrication(master_cv, tailored)` returns a list of invented items; the eval runner
fails any scenario where the list is non-empty.  See `tests/test_fabrication.py` and
`tests/test_fabrication_c.py` for coverage.
