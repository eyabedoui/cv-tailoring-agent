# B-WEB Implementation Progress

## Checklist

- [x] W1 — Allowlist consumers, job IDs, remove mock://
- [x] W2 — Flask apply site + static export
- [x] W3 — Browser Use search client
- [x] W4 — Firecrawl read + parse_posting
- [x] W4b — Upgrade match_skills (word boundaries, French aliases)
- [x] W5 — Browser Use submit
- [x] W6 — Throttle, fault modes, usage log
- [x] W7 — Snapshots and replay mode
- [x] W8 — Setup, smoke test, docs
- [x] W9 — Offline autouse fixture, dead code removal

## Phase Notes

### W9 — done (2026-11-20)

- `tests/conftest.py` gains `_offline_guard` autouse fixture: sets `WEB_MODE=fake`, clears `FAULT_MODE`, and resets throttle state after every test. Tests that need live behaviour override with `monkeypatch.setenv("WEB_MODE", "live")`.
- Dead code audit: no `LiveSearchClient`, `_LiveNotImplemented`, or placeholder "not yet implemented" strings remain in `agent/`.
- Gate: **596 passed** (unchanged — fixture adds no new tests), eval 15/15.

### W8 — done (2026-11-20)

- `sandbox/manage.py::setup_web()` added: runs `python -m playwright install chromium`; non-fatal on failure. Added as `python -m sandbox setup-web` subcommand.
- `tests/test_w8_smoke.py`: 20 smoke tests covering imports, protocol conformance, factory wiring for all W3–W7 clients, replay mode, throttle, and usage log.
- `docs/sandbox.md` updated: WEB_MODE table, env vars, `snapshot` and `setup-web` commands, replay mode workflow, throttle + usage log descriptions.
- Gate: **596 passed** (↑20 from W7 576), eval 15/15.

### W7 — done (2026-11-19)

- `FakePostingClient._fetch_snapshot(url)` added: hashes URL to `<site>-<8hex>` job_id, reads `sandbox/snapshots/<job_id>.json`, returns `{"markdown": ..., "url": ...}`.
- `FakePostingClient.fetch()` routes non-own-site URLs to `_fetch_snapshot` when `WEB_MODE=replay`; own-site URLs always use `postings/`.
- `sandbox/manage.py::snapshot(url, snapshots_dir)` fetches with FirecrawlPostingClient and saves `{url, job_id, markdown}` to `sandbox/snapshots/<job_id>.json`.
- `python -m sandbox snapshot <url>` subcommand added.
- Gate: **576 passed** (↑11 from W6 565), eval 15/15.

### W6 — done (2026-11-19)

- `agent/tools/throttle.py`: `throttle(host, seconds)` enforces `SITE_THROTTLE_SECONDS` gap between consecutive requests to the same host; uses `None` sentinel for first call; clock injectable for tests via `_throttle_mod._clock`.
- `agent/tools/usage_log.py`: `log_usage(tool, host, status, detail, _log_path)` appends JSON lines to `sandbox/usage_log.jsonl`; OSError is swallowed.
- `find_jobs`, `read_job_posting`, `submit_application` call throttle + log_usage when `WEB_MODE=live` and no injected client; offline tests unaffected.
- Gate: **565 passed** (↑16 from W5 549), eval 15/15.

### W5 — done (2026-11-19)

- `BrowserSubmitClient` added to `clients.py`; navigates to `own_apply_url(job_id)` and clicks `#submit-application` via browser-use; returns `{"status": "submitted", "application_id": ...}` or `PORTAL_DOWN` on failure.
- `submit_application` updated with optional `_submit_client` parameter; routes to `BrowserSubmitClient` for `WEB_MODE=live` or when `_submit_client` is injected; retains direct portal path for `fake` mode.
- Fault injection fires before the submit client call in all modes.
- Gate: **549 passed** (↑10 from W4 539), eval 15/15.

### W4 / W4b — done (2026-11-19)

- `FirecrawlPostingClient` added to `clients.py`; uses `V1FirecrawlApp(api_key).scrape_url(url, formats=["markdown"])`. Returns `{"markdown": ..., "url": ...}`.
- `parse_posting(markdown, url)` added to `reads.py`; extracts title, company, requirements, text, job_id from scraped markdown. External URLs get `<site>-<8hexhash>` job_id.
- `read_job_posting` updated: when `_posting` is None, calls `parse_posting` on the returned markdown.
- W4b: `_skill_present` upgraded to `_word_match` (custom word-boundary regex); `_SKILL_ALIASES` extended with French aliases (`tests unitaires`, `analyse de données`, `résolution de problèmes`, `travail en équipe`, `api rest`, etc.).
- Gate: **539 passed** (↑33 from W3 506), eval 15/15.

### W3 — done (2026-11-19)

- `BrowserSearchClient` added to `agent/tools/clients.py`; uses `browser_use.Agent` with a `_SearchOutput` Pydantic output schema to collect up to 10 job listings per site.
- `_get_search_client()` in `search.py` returns `BrowserSearchClient()` for `WEB_MODE=live`; `FakeSearchClient` for all other modes.
- Removed `LiveSearchClient` placeholder and `_LiveNotImplemented`; `browser-use>=1.0` added to `requirements.txt`.
- Gate: **506 passed** (↑12 from W2 494), eval 15/15.

### W2 — done (2026-11-19, revised)

- `GET /jobs/<id>` → HTML (Jinja2, autoescape ON, no `|safe`); `GET /jobs/<id>.json` → JSON for agent.
- `GET /apply/<id>` → read-only HTML: CV + cover letter in `<pre>` (escaped), single `<button id="submit-application">`, no editable inputs; shows "Already applied." without button when duplicate; 404 "not saved yet" if output files missing; 400 on invalid job_id format.
- `POST /apply/<id>` → paths derived from job_id (no client-supplied paths); checks file existence, duplicate → 409; works from empty form body.
- `export-static [--dest sandbox/site] [--postings-dir]` → `index.html` + `jobs/<id>.html` per posting; reads ALL .json (includes injection postings); same Jinja2 template as live server; autoescape ON; `sandbox/site/` added to `.gitignore`.
- `docs/sandbox.md`: documented Flask routes and static export URL shapes (GitHub Pages compatible).
- Restored 5 tests accidentally dropped in W1 migration (`test_fault_modes.py`): `test_unknown_fault_on_submit`, `test_no_fault_mode_read_succeeds`, `test_no_fault_mode_submit_succeeds`, `test_check_fault_empty_string_returns_none`, `test_check_fault_reject_duplicate_only_fires_for_submit`.
- Gate: **494 passed** (↑52 from W1 442, test floor now 494), eval 15/15.

---

## Final Report (audit 2026-11-20)

### Per-phase status (W3–W9)

| Phase | Status | Key evidence (test names) |
|---|---|---|
| W3 Browser search | Done | `test_browser_search_client.py` — `test_search_returns_list`, `test_search_query_sent_to_agent`; `test_w8_smoke.py` — `test_get_search_client_live_is_browser` |
| W4 Firecrawl read | Done | `test_firecrawl_posting_client.py` — `test_firecrawl_fetch_returns_markdown`, `test_firecrawl_fault_fires_before_fetch`; `test_parse_posting.py` — parse & match round-trip |
| W4b FR aliases | Done | `test_match_skills_upgrade.py` — 25 parametrized posting scores, bidirectional EN↔FR alias tests |
| W5 Browser submit | Done | `test_browser_submit_client.py` — `test_browser_submit_returns_submitted`, `test_submit_application_uses_submit_client_when_injected` |
| W6 Throttle + log | Done | `test_throttle.py` — 10 tests; `test_usage_log.py` — 8 tests |
| W7 Snapshots | Done | `test_snapshots.py` — `test_snapshot_saved`, `test_replay_mode_uses_snapshot` |
| W8 Setup + smoke | Done | `test_w8_smoke.py` — 20 tests covering imports, factory wiring, replay, throttle, usage log |
| W9 Offline guard | Done | `conftest.py` `_offline_guard` autouse; `test_fault_modes_web.py` — `test_web_mode_is_fake_in_pytest_environment` |

### Library versions used

| Library | Version (lower bound in requirements.txt) |
|---|---|
| browser-use | 1.0.6 (`>=1.0`) |
| firecrawl-py | 4.57.0 (`>=4.0`) |
| Flask | 3.0.3 (`>=3.0`) |
| pydantic | 2.14.3 (`>=2.0`) |

> `V1FirecrawlApp` (not `FirecrawlApp`) is the correct class in firecrawl-py ≥ 4.x.
> `browser_use.Agent` with `output_model_schema=` and `.structured_output` property is the 1.0.x API.

### What is fake-only (never hits the network in the test suite)

- `BrowserSearchClient` — monkeypatched via `browser_use.Agent` in tests
- `FirecrawlPostingClient` — monkeypatched via `firecrawl.V1FirecrawlApp` in tests
- `BrowserSubmitClient` — monkeypatched via `browser_use.Agent` in tests
- All tests run with `WEB_MODE=fake` enforced by `_offline_guard` autouse fixture in `conftest.py`
- `FAULT_MODE` is cleared and throttle state is reset after every test

### Manual steps the user must perform before a live run

1. `pip install -r requirements.txt` — install all dependencies
2. `python -m sandbox setup` — creates dirs + installs Playwright Chromium (idempotent)
3. `python -m sandbox seed` — populate sandbox/postings/ with 25 job postings
4. Set `OPENAI_API_KEY` and `FIRECRAWL_API_KEY` in `.env` (copy from `.env.example`)
5. `python -m sandbox serve` — start the Flask apply site (required for `WEB_MODE=live` submit)
6. Optionally run `python -m sandbox smoke-web` to verify the full live stack

---

### W1 — done (2026-11-19)

- Added "own" site entry (kind=own, no host) to `allowed_sites.json`; `site_names()` and `is_url_allowed()` skip it.
- New helpers: `own_base_url()`, `own_job_url()`, `own_apply_url()`, `is_own_url()` in `sites.py`.
- `PostingClient` protocol + `FakePostingClient` in `agent/tools/clients.py`; fault injection moved inside the client.
- `ReadJobPostingIn` validator accepts own-site `/jobs/<id>` URLs and allowlisted https URLs; `mock://` removed everywhere in active source.
- `is_valid_job_id()` accepts both `job_NNN` and `<site>-<8hex>`; widened validators in `schemas.py`.
- `config.py`: removed `ALLOWED_URL_PREFIX`; added `WEB_MODE`, `OWN_SITE_BASE_URL`, `MAX_JOBS_PER_SEARCH`, throttle + browser settings.
- All 15 eval scenarios, all test files, CLI defaults, and eval runner migrated from `mock://` to `own_job_url()`.
- Gate: 442 tests pass (↑ from prior phases), eval 15/15, no mock:// or ALLOWED_URL_PREFIX in active source.
