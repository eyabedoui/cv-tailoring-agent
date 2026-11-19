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

## Tool contract (unchanged)

| Tool | Returns |
|------|---------|
| `read_job_posting(url)` | `job_id, title, company, requirements, text` |
| `read_master_cv()` | `text, sections` |
| `match_skills(cv_text, job)` | `matched, missing, score` (0–1) |
| `check_format(cv_text)` | `ok, issues` |
| `save_tailored_cv(text, job_id, kind: "cv"\|"cover_letter")` | `path, saved` |
| `submit_application(cv_path, cover_letter_path, job_id)` | `status, application_id` |

`TOOL_SCHEMAS` and `execute_tool(name, args)` in `agent/tools/registry.py` are the
canonical registry interface. Tool names must never be renamed.

## Mock URLs
Only `mock://jobs/<id>` URLs are accepted by the stub tools.
Real URLs will be handled by Person B's implementations.

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
- `make setup` — `pip install -r requirements.txt`
- `make run`   — `python -m agent --model openai --auto-approve`

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

Errors are dicts `{"error": CODE, "message": "...", "retryable": bool}`.
Messages are plain text the model can act on — never stack traces.
Failed tool results are sent back to the model; state is NOT updated on error.

## Checkpoint timeout
`CHECKPOINT_TIMEOUT_SECONDS = 120`. Interactive input is collected in a daemon
thread; on timeout the checkpoint treats the submission as rejected and the loop
returns `stop_reason = "checkpoint_timeout"`.

## Definition of done
- Merged to `main`.
- `python -m pytest -q` exits 0.
- Handoff note appended to `problems.md`.
- Reviewed and signed off by the next person.
