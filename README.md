# CV Tailoring Agent

CS496 AI Engineering — Project 3.

An agentic pipeline that reads a job posting and a master CV, tailors the CV and
cover letter to the job, and submits the application only after explicit human
approval.

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill in ANTHROPIC_API_KEY
```

## Run

```bash
# Full run with real model (requires API key)
python -m agent --job-url mock://jobs/job_001

# Demo run with no API key required
python -m agent --model fake --auto-approve

# See all options
python -m agent --help
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
