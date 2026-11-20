# CV Tailoring Agent

CS496 AI Engineering — Project 3.

An agentic pipeline that reads a job posting and a master CV, tailors the CV and
cover letter to the job, and submits the application only after explicit human
approval.

---

## Setup

One command installs dependencies, seeds the sandbox, and installs Playwright Chromium (needed only for live web mode):

```bash
pip install -r requirements.txt
python -m sandbox setup
python -m sandbox seed
```

For **live web scraping** you also need API keys.  Copy the example env file and fill in the values:

```bash
cp .env.example .env
# edit .env and set:
#   OPENAI_API_KEY    – from platform.openai.com
#   FIRECRAWL_API_KEY – from firecrawl.dev
```

Keys needed and when:

| Key | When needed |
|---|---|
| `OPENAI_API_KEY` | Real model runs (`--model real`) and live browser search/submit (`WEB_MODE=live`) |
| `FIRECRAWL_API_KEY` | Live job-page scraping (`WEB_MODE=live`) and `python -m sandbox snapshot` |

## Run (chat mode)

```bash
# Interactive chat (requires OPENAI_API_KEY)
python -m agent chat --job-url http://127.0.0.1:5000/jobs/job_001

# Demo without any API key (fake model, auto-approval)
python -m agent --model fake --auto-approve

# See all options
python -m agent --help
```

## Replay mode (offline, no keys)

Record real job pages once (needs FIRECRAWL_API_KEY):

```bash
python -m sandbox snapshot https://www.keejob.com/offres-emploi/12345
```

Then run the agent against the saved snapshot — no API keys required:

```bash
set WEB_MODE=replay
python -m agent --job-url https://www.keejob.com/offres-emploi/12345
```

## Reset sandbox

```bash
python -m sandbox reset   # clears output/ and state/ (keeps postings)
python -m sandbox seed    # re-seeds postings (idempotent)
```

## Windows — no make

All commands use `python -m ...` directly; there is no Makefile dependency.  Run tests with:

```bat
python -m pytest -q
python -m eval.runner --model fake
python scripts/scan_secrets.py
```

## Results

_To be filled in after evaluation._

---

## Contributions

| Person | Role |
|--------|------|
| Person A | Agent core: loop, checkpoint, logger, error contract, model adapter |
| Person B | Tools, portal scraper, Pydantic schemas, Makefile, evaluation |

## Team Roles

- **Person A** owns `agent/` and `tests/`.
- **Person B** owns `eval/`, the real tool implementations, and the job portal.

## Pull request rules

- Work on a branch, never directly on `main`.
- Every PR needs at least one teammate review before merging.
- All tests must pass before merging.
- Never commit API keys, `.env` files, logs or real personal data.
- Every bug fix adds an entry to `problems.md`.
