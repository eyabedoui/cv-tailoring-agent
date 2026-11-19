# Sandbox job postings

25 fictional postings (job_001 – job_025).  All companies are invented;
all contacts use `example.invalid` domains.  No real data, no network access.

Expected match scores are computed by the stub `match_skills` implementation
(simple case-insensitive substring matching against `master_cv.md`).

| job_id  | Title                             | Company                           | Requirements                                            | Expected score |
|---------|-----------------------------------|-----------------------------------|---------------------------------------------------------|----------------|
| job_001 | Junior AI Engineer                | TechNova Solutions (fictional)    | Python, machine learning, Data analysis, Problem solving | 0.75           |
| job_002 | Full-Stack Web Developer          | Brightware Labs (fictional)       | Python, JavaScript, React, SQL                          | 1.00           |
| job_003 | Systems Engineer                  | Ironclad Systems (fictional)      | Java, C++, Go, Rust                                     | 0.00           |
| job_004 | Data Analyst                      | Nexagen Analytics (fictional)     | Python, SQL, pandas, NumPy                              | 1.00           |
| job_005 | DevOps Engineer                   | Cloudrift Inc (fictional)         | Docker, Kubernetes, AWS, Terraform                      | 0.00           |
| job_006 | Frontend Developer                | Prismix Design (fictional)        | JavaScript, React, HTML/CSS, unit testing               | 1.00           |
| job_007 | Backend Python Developer          | Vortex Technologies (fictional)   | Python, Flask, REST APIs, unit testing                  | 1.00           |
| job_008 | Machine Learning Engineer         | DeepMind Fictions (fictional)     | TensorFlow, PyTorch, Python, deep learning              | 0.25           |
| job_009 | Database Administrator            | DataVault Corp (fictional)        | SQL, MongoDB, Redis, Python                             | 0.50           |
| job_010 | Big Data Engineer                 | StreamFlow Data (fictional)       | Spark, Kafka, Scala, Python                             | 0.25           |
| job_011 | Security Analyst                  | CipherShield Inc (fictional)      | Python, Linux, Bash, problem solving                    | 1.00           |
| job_012 | Cloud Architect                   | NimbusCloud (fictional)           | AWS, Azure, Google Cloud Platform, Terraform            | 0.00           |
| job_013 | API Developer                     | ConnectAPI Corp (fictional)       | Python, REST APIs, Flask, Git                           | 1.00           |
| job_014 | Research Software Engineer        | OpenIntel Labs (fictional)        | Python, pandas, NumPy, problem solving                  | 1.00           |
| job_015 | Technical Teaching Assistant      | EduTech Corp (fictional)          | Python, SQL, communication, teamwork                    | 1.00           |
| job_016 | Stream Processing Developer       | DataStream Processing (fictional) | Scala, Kafka, Python, Spark                             | 0.25           |
| job_017 | Web Application Developer         | CraftWeb Studio (fictional)       | JavaScript, HTML/CSS, React, Node.js                    | 1.00           |
| job_018 | Infrastructure Automation Engineer| GridCore (fictional)              | Docker, Kubernetes, Linux, Bash                         | 0.50           |
| job_019 | GraphQL API Developer             | QueryCraft (fictional)            | GraphQL, JavaScript, Node.js, REST APIs                 | 0.75           |
| job_020 | Rust Systems Developer            | LowLevel Labs (fictional)         | Rust, C++, Go, Linux                                    | 0.25           |
| job_021 | Junior Software Developer         | StartBright Tech (fictional)      | Python, SQL, Git, problem solving                       | 1.00           |
| job_022 | AI Applications Developer         | CogniApp (fictional)              | Python, machine learning, problem solving, data analysis| 0.75           |
| job_023 | Quality Assurance Engineer        | QualityFirst Corp (fictional)     | Python, unit testing, Bash, SQL                         | 1.00           |
| job_024 | Cloud-Native Developer            | CloudSoft Inc (fictional)         | Python, AWS, React, SQL                                 | 0.75           |
| job_025 | Data Science Intern               | Insight Analytics (fictional)     | Python, pandas, NumPy, SQL                              | 1.00           |

## Notes

- Scores ≥ 0.25 pass the `NO_MATCH_THRESHOLD` and allow the agent to continue.
- job_003, job_005, job_012 score 0.00 — the agent will stop early with `no_match`.
- job_008, job_010, job_016, job_020 score 0.25 — exactly at the threshold (not below it, so the agent continues).
- job_001, job_019, job_022, job_024 score 0.75 — good fit with one or two skill gaps to address.

## Regenerating postings

```
python -m sandbox.seed
```

## Flask apply site (live mode)

Start with `python -m sandbox serve [--port 5000]`.

| URL pattern | Method | Description |
|---|---|---|
| `/health` | GET | Health check — returns `{"status":"ok"}` |
| `/jobs/<job_id>` | GET | HTML job posting page |
| `/jobs/<job_id>.json` | GET | JSON job posting (for the agent) |
| `/apply/<job_id>` | GET | Read-only view of saved CV + cover letter; shows submit button unless already applied or files missing |
| `/apply/<job_id>` | POST | Record the application; paths derived from `job_id`; returns JSON |

Default base URL: `http://127.0.0.1:5000` (loopback only).  
Configured via `OWN_SITE_BASE_URL` environment variable.

## Static export

Export all postings as a self-contained static HTML site:

```
python -m sandbox export-static [--dest sandbox/site] [--postings-dir sandbox/postings]
```

Output layout (relative to `--dest`):

```
index.html              ← listing of all postings
jobs/<job_id>.html      ← individual posting page (same template as live /jobs/<job_id>)
```

The export reads **every** `*.json` file from `--postings-dir`, so injection postings
(`job_901+`) placed there are included automatically.

**GitHub Pages URL shape** — if `OWN_SITE_BASE_URL = https://user.github.io/cv-agent-sandbox`:

| Path | Full URL |
|---|---|
| `index.html` | `https://user.github.io/cv-agent-sandbox/` |
| `jobs/job_001.html` | `https://user.github.io/cv-agent-sandbox/jobs/job_001.html` |

The `sandbox/site/` directory is listed in `.gitignore` and is not committed.

---

## Web mode (B-WEB phases W3–W7)

Set the `WEB_MODE` environment variable to control which clients are used:

| `WEB_MODE` | Search client | Posting client | Submit |
|---|---|---|---|
| `fake` (default) | `FakeSearchClient` (sandbox postings) | `FakePostingClient` (sandbox postings) | Portal direct |
| `replay` | `FakeSearchClient` | `FakePostingClient` reads `sandbox/snapshots/` for external URLs | Portal direct |
| `live` | `BrowserSearchClient` (browser-use + OpenAI) | `FirecrawlPostingClient` (Firecrawl) | `BrowserSubmitClient` (browser-use) |

### Environment variables for `WEB_MODE=live`

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Required by `BrowserSearchClient` and `BrowserSubmitClient` |
| `FIRECRAWL_API_KEY` | Required by `FirecrawlPostingClient` and the `snapshot` command |
| `SEARCH_LLM_MODEL` | Model for search (default: `gpt-4o-mini`) |
| `SUBMIT_LLM_MODEL` | Model for submit (default: `gpt-4o-mini`) |
| `OWN_SITE_BASE_URL` | Base URL for the Flask apply site (default: `http://127.0.0.1:5000`) |

### New sandbox commands

```
python -m sandbox setup-web               – install Playwright Chromium (needed for live browser automation)
python -m sandbox snapshot <url>          – fetch URL with Firecrawl and save to sandbox/snapshots/<job_id>.json
python -m sandbox snapshot <url> --snapshots-dir PATH  – save to a custom directory
```

### Replay mode workflow

1. Record real job pages once (needs `FIRECRAWL_API_KEY`):
   ```
   python -m sandbox snapshot https://www.keejob.com/offres-emploi/12345
   ```

2. Run the agent with `WEB_MODE=replay` (no API keys needed):
   ```
   WEB_MODE=replay python -m agent --job-url https://www.keejob.com/offres-emploi/12345
   ```

Snapshots are stored as `sandbox/snapshots/<site>-<8hexhash>.json` keyed by a SHA-256 hash of the URL.

### Throttle and usage log

- `SITE_THROTTLE_SECONDS` (default: 3.0) enforces a minimum gap between consecutive requests to the same host in live mode.
- Each live tool call appends a JSON entry to `sandbox/usage_log.jsonl` with `timestamp`, `tool`, `host`, and `status`.
