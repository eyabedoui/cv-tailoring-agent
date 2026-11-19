# Allowed Sites

The agent may only search, read, and submit to the sites listed here.

## Site Registry (`agent/allowed_sites.json`)

| Name | Host | Kind | Searchable | Purpose |
|---|---|---|---|---|
| tanitjobs | www.tanitjobs.com | external | yes | Job board (Tunisia) |
| keejob | www.keejob.com | external | yes | Job board (Maghreb) |
| weworkremotely | weworkremotely.com | external | yes | Remote job board |
| own | (from env) | own | no | Candidate-facing apply site |

Subdomain matching is enabled: e.g. `jobs.weworkremotely.com` resolves to the `weworkremotely` entry.

## Own Site

The candidate's own apply site URL is configured via the `OWN_SITE_BASE_URL` environment variable.

Default: `http://127.0.0.1:5000` (loopback; http is allowed only for loopback addresses).

| Path pattern | Purpose |
|---|---|
| `{base}/jobs/<job_id>` | View a job posting |
| `{base}/apply/<job_id>` | Submit an application |

The own site is **not** searchable via `find_jobs`. Applications may only be submitted to the own site — never to external job boards.

## Security Rules

1. `https://` is required for all external sites; http is refused.
2. Loopback own site (`127.0.0.1`, `localhost`) may use `http://`.
3. URLs containing userinfo (e.g. `https://user:pass@host`) are refused.
4. Lookalike hostnames (e.g. `weworkremotely.com.evil.io`) are refused.
5. All untrusted content from external sites is wrapped with `wrap_untrusted()`.

## Adding a New Site

1. Add an entry to `agent/allowed_sites.json` with `"enabled": true`.
2. Set `"host"` to the canonical hostname (without protocol or trailing slash).
3. Clear `_load_allowlist_cached` LRU cache if running in a long-lived process.
4. Add tests to `tests/test_sites.py` covering the new host.
