# Deployment

Status: **not deployed yet.** Public URL: TBD (add it here and in the README once the host is running).

## What runs where

One container runs two processes (`start.sh`):

| Piece | Where | Why |
|---|---|---|
| Chat and agent (Chainlit) | Public port (`PORT`, default 7860) | Candidates and the grader use it from a browser |
| Our apply site (Flask) | `127.0.0.1:5000`, inside the container only | Browser Use submits here; a static site cannot accept a POST |
| Static job postings | GitHub Pages (`python -m sandbox export-static`) | Firecrawl runs in the cloud and cannot reach localhost |

`OWN_SITE_BASE_URL` stays `http://127.0.0.1:5000` inside the container. The postings the agent reads from the
web come from the GitHub Pages address.

## Environment variables (set in the host's settings, never in the repository)

| Variable | Required | Meaning |
|---|---|---|
| `APP_USERNAME`, `APP_PASSWORD` | yes | Chat login. `start.sh` refuses to start without them |
| `CHAINLIT_AUTH_SECRET` | yes | Signs login sessions. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `WEB_MODE` | no | `replay` (default in the image), `live` or `fake` |
| `CV_AGENT_MODEL` | no | `fake` (default, scripted, no spend) or `openai` |
| `OPENAI_API_KEY` | live only | Needed when `CV_AGENT_MODEL=openai` or `WEB_MODE=live` |
| `FIRECRAWL_API_KEY` | live only | Needed for live page reading |
| `API_BUDGET_USD` | no | Spending guard in `agent/config.py`; 0 blocks paid calls |
| `PORT` | no | Public port, default 7860 |
| `ALLOW_NO_AUTH` | local tests only | `1` skips the login check. Never set it on a public host |

## Build and test locally

```
docker build -t cv-agent .
docker run --rm -p 7860:7860 \
  -e APP_USERNAME=demo -e APP_PASSWORD=choose-one -e CHAINLIT_AUTH_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))") \
  cv-agent
```
Open http://localhost:7860 and log in. The image is replay-only: it does not install a browser. Live Browser Use runs (`WEB_MODE=live`) need a browser, and `--build-arg INSTALL_CHROMIUM=1` currently fails because the playwright package is not installed. Fix that before any live deployment.

Without Docker: `ALLOW_NO_AUTH=1 sh start.sh` starts the same two processes.

## Deploy on a host

1. Choose a host that runs a container or a Python app. Check the free-tier memory (headless Chromium needs
   some) and whether the service sleeps when idle.
2. Point it at this repository's `Dockerfile` and set the public port to the value of `PORT`.
3. Add the variables above in the host's environment settings.
4. Keep `WEB_MODE=replay` and `CV_AGENT_MODEL=fake` until the full chat below works. Switch to live only for the
   demo and graded runs.
5. Set the spending limits on the OpenAI and Firecrawl dashboards before sharing the URL.

## Switching live and replay

Change `WEB_MODE` and `CV_AGENT_MODEL` in the host's settings and restart the service. No code change is needed.

## Restart

Use the host's restart button. `start.sh` resets the sandbox state and re-seeds the postings on every start, so a
restart gives a clean demo.

## Checks before sharing the URL

1. `python scripts/scan_secrets.py` reports no secrets (it scans every git-tracked file, so the Dockerfile and
   `start.sh` are included once committed).
2. Logs and error messages never print keys (the logger redacts key-like fields; check one real error by hand).
3. Open the URL in a private window: the login page must appear before the chat.
4. One full chat on the public URL: search, read, tailor, click Approve, submit, then confirm the portal record
   (`sandbox/state/applications.json` inside the container, or the apply site's own status).
5. Replay subset (DEP3): through the public chat, run a good match, a rejected application, a LinkedIn request
   (must be refused), a posting with an injection (must not be obeyed) and a missing job. Write any failure in
   `problems.md`.
