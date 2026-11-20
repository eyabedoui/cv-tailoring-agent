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

##  Terms and Robots Verification

Verification date: 2026-11-20

### Tanitjobs

- Host: www.tanitjobs.com
- robots.txt: https://www.tanitjobs.com/robots.txt
- Terms: https://www.tanitjobs.com/terms-of-use/
- robots.txt findings: Public job pages are generally allowed. Resume, administration, and certain parameterized search URLs are disallowed.
- Terms findings: Personal, non-commercial viewing is permitted within stated limits. Disruptive activity and unreasonable infrastructure load are prohibited. Automated scraping is not explicitly authorized.
- Decision: PENDING CLARIFICATION. Do not run live automated scraping until the intended access is confirmed permissible.
- Restrictions: No login, no resume access, no external submissions, no disallowed search URLs, and no excessive requests.


### Keejob

- Host: www.keejob.com
- Verification date: 2026-11-20
- robots.txt: https://www.keejob.com/robots.txt
- Terms: https://www.keejob.com/terms-of-use/
- robots.txt findings: Public job listings are not generally disallowed. API endpoints, account pages, recruiter areas, application endpoints, and certain query parameters are restricted.
- Terms findings: Website content and databases are protected by intellectual property laws. Automated scraping is not explicitly authorized or prohibited in the reviewed terms.
- Decision: PENDING CLARIFICATION before live automated access.
- Restrictions: No login, no external application submission, no restricted paths, and no bulk extraction.
- Fallback: emploi.nat.tn if Keejob cannot be used.



### We Work Remotely

- Host: weworkremotely.com
- Verification date: 2026-11-20
- robots.txt: https://weworkremotely.com/robots.txt
- Terms: https://weworkremotely.com/terms-and-conditions
- Terms last updated: 2026-10-23
- robots.txt findings: Public job pages are generally allowed. Administration, account, profile, and company management pages are disallowed, along with specified token-based editing and cancellation URLs.
- Terms findings: Website materials are protected by intellectual property laws. Users receive a limited, revocable right to access and use materials. Explicit authorization for automated scraping was not identified.
- Decision: PENDING CLARIFICATION before live automated access.
- Restrictions: No login, no account access, no external applications, no restricted paths, and no bulk extraction.