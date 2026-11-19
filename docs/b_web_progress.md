# B-WEB Implementation Progress

## Checklist

- [x] W1 — Allowlist consumers, job IDs, remove mock://
- [ ] W2 — Flask apply site + static export
- [ ] W3 — Browser Use search client
- [ ] W4 — Firecrawl read + parse_posting
- [ ] W4b — Upgrade match_skills (word boundaries, French aliases)
- [ ] W5 — Browser Use submit
- [ ] W6 — Throttle, fault modes, usage log
- [ ] W7 — Snapshots and replay mode
- [ ] W8 — Setup, smoke test, docs
- [ ] W9 — Offline autouse fixture, dead code removal

## Phase Notes

### W1 — done (2026-11-19)

- Added "own" site entry (kind=own, no host) to `allowed_sites.json`; `site_names()` and `is_url_allowed()` skip it.
- New helpers: `own_base_url()`, `own_job_url()`, `own_apply_url()`, `is_own_url()` in `sites.py`.
- `PostingClient` protocol + `FakePostingClient` in `agent/tools/clients.py`; fault injection moved inside the client.
- `ReadJobPostingIn` validator accepts own-site `/jobs/<id>` URLs and allowlisted https URLs; `mock://` removed everywhere in active source.
- `is_valid_job_id()` accepts both `job_NNN` and `<site>-<8hex>`; widened validators in `schemas.py`.
- `config.py`: removed `ALLOWED_URL_PREFIX`; added `WEB_MODE`, `OWN_SITE_BASE_URL`, `MAX_JOBS_PER_SEARCH`, throttle + browser settings.
- All 15 eval scenarios, all test files, CLI defaults, and eval runner migrated from `mock://` to `own_job_url()`.
- Gate: 442 tests pass (↑ from prior phases), eval 15/15, no mock:// or ALLOWED_URL_PREFIX in active source.
