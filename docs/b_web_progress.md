# B-WEB Implementation Progress

## Checklist

- [x] W1 — Allowlist consumers, job IDs, remove mock://
- [x] W2 — Flask apply site + static export
- [ ] W3 — Browser Use search client
- [ ] W4 — Firecrawl read + parse_posting
- [ ] W4b — Upgrade match_skills (word boundaries, French aliases)
- [ ] W5 — Browser Use submit
- [ ] W6 — Throttle, fault modes, usage log
- [ ] W7 — Snapshots and replay mode
- [ ] W8 — Setup, smoke test, docs
- [ ] W9 — Offline autouse fixture, dead code removal

## Phase Notes

### W2 — done (2026-11-19, revised)

- `GET /jobs/<id>` → HTML (Jinja2, autoescape ON, no `|safe`); `GET /jobs/<id>.json` → JSON for agent.
- `GET /apply/<id>` → read-only HTML: CV + cover letter in `<pre>` (escaped), single `<button id="submit-application">`, no editable inputs; shows "Already applied." without button when duplicate; 404 "not saved yet" if output files missing; 400 on invalid job_id format.
- `POST /apply/<id>` → paths derived from job_id (no client-supplied paths); checks file existence, duplicate → 409; works from empty form body.
- `export-static [--dest sandbox/site] [--postings-dir]` → `index.html` + `jobs/<id>.html` per posting; reads ALL .json (includes injection postings); same Jinja2 template as live server; autoescape ON; `sandbox/site/` added to `.gitignore`.
- `docs/sandbox.md`: documented Flask routes and static export URL shapes (GitHub Pages compatible).
- Restored 5 tests accidentally dropped in W1 migration (`test_fault_modes.py`): `test_unknown_fault_on_submit`, `test_no_fault_mode_read_succeeds`, `test_no_fault_mode_submit_succeeds`, `test_check_fault_empty_string_returns_none`, `test_check_fault_reject_duplicate_only_fires_for_submit`.
- Gate: **494 passed** (↑52 from W1 442, test floor now 494), eval 15/15.

### W1 — done (2026-11-19)

- Added "own" site entry (kind=own, no host) to `allowed_sites.json`; `site_names()` and `is_url_allowed()` skip it.
- New helpers: `own_base_url()`, `own_job_url()`, `own_apply_url()`, `is_own_url()` in `sites.py`.
- `PostingClient` protocol + `FakePostingClient` in `agent/tools/clients.py`; fault injection moved inside the client.
- `ReadJobPostingIn` validator accepts own-site `/jobs/<id>` URLs and allowlisted https URLs; `mock://` removed everywhere in active source.
- `is_valid_job_id()` accepts both `job_NNN` and `<site>-<8hex>`; widened validators in `schemas.py`.
- `config.py`: removed `ALLOWED_URL_PREFIX`; added `WEB_MODE`, `OWN_SITE_BASE_URL`, `MAX_JOBS_PER_SEARCH`, throttle + browser settings.
- All 15 eval scenarios, all test files, CLI defaults, and eval runner migrated from `mock://` to `own_job_url()`.
- Gate: 442 tests pass (↑ from prior phases), eval 15/15, no mock:// or ALLOWED_URL_PREFIX in active source.
