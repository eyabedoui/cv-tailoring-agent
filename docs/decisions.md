# Design Decisions

## Language and runtime
Python 3.12.

## Step limit
`MAX_STEPS = 12`. A **step** is one model decision that results in one tool call.
The human approval checkpoint and the final answer are NOT steps.

## No-match threshold
`NO_MATCH_THRESHOLD = 0.25`. If `match_skills` returns a score below 0.25 the
agent stops with `stop_reason = "no_match"` rather than tailoring an obviously
unsuitable application.

## Tool contract

| Tool | Returns |
|------|---------|
| `find_jobs(query, site)` | `jobs (list), site, count, truncated` |
| `read_job_posting(url)` | `job_id, title, company, requirements, text` |
| `read_master_cv()` | `text, sections` |
| `match_skills(cv_text, job)` | `matched, missing, score` (0–1) |
| `check_format(cv_text)` | `ok, issues` |
| `save_tailored_cv(text, job_id, kind: "cv"\|"cover_letter")` | `path, saved` |
| `submit_application(cv_path, cover_letter_path, job_id)` | `status, application_id` |

`TOOL_SCHEMAS` and `execute_tool(name, args)` in `agent/tools/registry.py` are the
canonical registry interface. Tool names must never be renamed.

`find_jobs` is read-only and NOT gated by the human checkpoint.
Only `submit_application` is gated.

## Mock URLs and site allowlist
`mock://jobs/<id>` URLs are accepted by the sandbox read tool.
For real job sites, only URLs from `agent/allowed_sites.json` are accepted:
- **tanitjobs** — www.tanitjobs.com
- **keejob** — www.keejob.com
- **weworkremotely** — weworkremotely.com

Non-allowlisted http/https URLs return `SITE_NOT_ALLOWED` from `read_job_posting`.
Live search is placeholder-only (`LiveSearchClient` raises `PORTAL_DOWN`).

## Candidate ID
One fixed candidate: `CANDIDATE_ID = "candidate_001"` (see `agent/config.py`).

## Repository layout

```
agent/          agent core (loop, checkpoint, logger, model, errors, prompts, config)
sandbox/        sandboxed output written by save_tailored_cv
eval/           evaluation scripts (Person B)
tests/          pytest suite
docs/           design docs and log format spec
README.md
errors.md       (Person B fills in portal-specific errors)
threat_model.md
report.pdf
postmortem.md
cost_model.md
problems.md     bug log
Makefile
requirements.txt
.gitignore
.env.example
```

## make targets
- `make install`   — `pip install -r requirements.txt`
- `make run`       — `python -m agent --model openai` (waits for human approval)
- `make run-auto`  — same but with `--auto-approve` (CI / demos only)
- `make demo-fake` — fake model, auto-approved, no API key required
- `make eval-fake` — run eval scenarios with fake model

Use `make PYTHON=python <target>` on Windows to override the Python binary.

## Model provider: OpenAI

- **Only one provider key is needed**: `OPENAI_API_KEY`. There is no Anthropic key.
- **JSON protocol kept**: the model returns one JSON object per reply (tool_call or
  final); no native function-calling is used. This keeps the loop provider-agnostic.
- **`max_completion_tokens` instead of `max_tokens`**: reasoning models (o1, o3, etc.)
  reject the `max_tokens` parameter. Using `max_completion_tokens` works for both
  standard and reasoning models. `temperature` and `top_p` are also omitted for the
  same reason.
- **`response_format: json_object` with fallback**: sent on the first call to get
  clean JSON. If the API returns a `BadRequestError` mentioning `response_format`
  (some older or fine-tuned models reject it), the adapter retries once without it
  and remembers that choice for the lifetime of the instance.
- **Other tool keys (Firecrawl, Browser Use) are separate**: they go in `.env` as
  `FIRECRAWL_API_KEY` and `BROWSER_USE_API_KEY`; the agent never reads them.
- **Browser Use uses OpenAI**: it wraps the OpenAI Chat Completions API internally,
  so `OPENAI_API_KEY` covers it too.

## Human checkpoint gate
Only `submit_application` is gated behind the human approval checkpoint.
Saving files to `sandbox/output` before approval is allowed (the sandbox resets).

## Error contract
See `agent/errors.py`. Error codes:

- `INVALID_ARGUMENTS` — wrong types or values passed to a tool
- `UNKNOWN_TOOL` — model requested a tool that does not exist
- `NOT_FOUND` — requested resource (URL, file) does not exist
- `EMPTY_POSTING` — job posting returned no usable content
- `PORTAL_DOWN` — job portal is unreachable
- `TIMEOUT` — operation exceeded time limit
- `BAD_RESPONSE` — model response could not be parsed
- `DUPLICATE_SUBMISSION` — application already submitted for this job
- `PATH_NOT_ALLOWED` — save path is outside the sandbox
- `SITE_NOT_ALLOWED` — URL or site name is not in the enabled allowlist (retryable=false)
- `SITE_BLOCKED` — site refused automation (captcha, login wall, 403/429); retryable=false

Errors are dicts `{"error": CODE, "message": "...", "retryable": bool}`.
Messages are plain text the model can act on — never stack traces.
Failed tool results are sent back to the model; state is NOT updated on error.

## Checkpoint timeout
`CHECKPOINT_TIMEOUT_SECONDS = 120`. Interactive input is collected in a daemon
thread; on timeout the checkpoint treats the submission as rejected and the loop
returns `stop_reason = "checkpoint_timeout"`.

## Session and chat checkpoint

- `Session(model, checkpoint, logger=None, on_step=None)` wraps `AgentLoop` for multi-turn
  chat. `send(user_text)` appends the user message, runs the loop, and rebuilds the shared
  history from the result's messages (system message stripped). Workflow state (`job`,
  `master_cv`, `tailored_cv`, `cover_letter`) is carried forward between turns via the loop's
  `state=` parameter. Per-turn step counters always reset; `MAX_STEPS_PER_SESSION = 40` caps
  the total across all turns. `reset()` clears history, state, and the step counter.
- History trimming: when `len(history) > MAX_HISTORY_MESSAGES` (60), oldest messages are
  dropped from the front. After trimming, the first message must be a `user` message; any
  leading non-user messages are also dropped.
- `ChatCheckpoint(present_fn, timeout_seconds)` replaces `HumanApprovalCheckpoint`'s
  interactive terminal prompt with a queue-based API: the agent loop blocks in
  `request_approval()` until `submit_decision(bool)` is called from the UI thread, or the
  timeout fires. `submit_decision` raises `TypeError` for non-bool values and silently ignores
  late decisions (called after `request_approval` has already returned).
- Quota 429 (error code `insufficient_quota` or message mentions credits/quota/billing) is
  treated as non-retryable: `OpenAIModel` raises `ModelUnavailableError` immediately without
  consuming retry attempts. `__main__.py` catches it, prints `Model unavailable: <message>`,
  and exits with code 2.
- `on_step` callback in `AgentLoop.__init__`: called after each tool execution and after the
  human checkpoint, with `{"step": n, "tool": name, "arguments": args, "result": result}`.
  Wrapped in try/except so a failing callback never crashes the loop.
- `run()` returns a `"state"` key on every return path (all 8 exit points), enabling the
  `Session` layer to initialise the next turn from the previous workflow state.

## Definition of done
- Merged to `main`.
- `python -m pytest -q` exits 0.
- Handoff note appended to `problems.md`.
- Reviewed and signed off by the next person.
