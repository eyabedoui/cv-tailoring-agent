# 1. System overview and web stack

The CV Tailoring Agent is a chat assistant. The candidate asks for jobs in a Chainlit window. The agent searches one
allowed job site, reads the posting the candidate picks, writes a tailored CV and cover letter from the candidate's master
CV, and shows both for review. Nothing is submitted until the candidate clicks **Approve**. A typed "yes" never counts.

## 1.1 What each service does

| Service | Used for | What it returns or writes |
|---|---|---|
| **Browser Use** (headless Chromium, driven by an OpenAI model) | **Searching.** `find_jobs` opens one site's home page, types the query and collects up to 10 listings (title, company, location, URL, short snippet). Also **submitting**, on our own apply site only, and only after approval. | Structured JSON. It reads and clicks; it never logs in or downloads. |
| **Firecrawl** | **Reading.** `read_job_posting` scrapes the one posting URL the candidate chose. | Markdown of that page. One scrape per posting, no crawling. |
| **Parser and cleaner** (`posting_cleaner.py`, `parse_posting` in `reads.py`) | Turn scraped markdown into title, company and a requirements list. | Navigation, cookie banners, ads, hidden text and zero-width characters are removed first. A small model is called only when heading rules fail. |
| **OpenAI model** (`gpt-4o-mini` by default) | The agent's own reasoning, plus the Browser Use browser. | Tool calls and the tailored CV and cover letter. |
| **Our Flask apply site** (`127.0.0.1:5000`) | The only place an application is ever submitted. | `sandbox/output/` holds the saved CV and cover letter. The portal's `applications.json` is the record of truth. |

Reading is split from searching on purpose. Browser Use is flexible but costs more tokens and time (step limit and
timeout per request). Firecrawl is a cheap, predictable single scrape of a URL we already have. Success of a submission is
decided by the portal record, not by what the browser agent reports.

## 1.2 Why three sites

| Site | Why it is included |
|---|---|
| Tanitjobs | Tunisian market, mostly French |
| Keejob | Tunisian market, French and English |
| We Work Remotely | Remote jobs in English |

Two Tunisian boards and one remote board cover the languages our candidates will meet, so the parser and the
French-language cases are tested on real pages. Access is read-only. `www.tanitjobs.com`, `www.keejob.com` and
`weworkremotely.com` are the only external hosts the code accepts. Anything else, LinkedIn included, is refused with
`SITE_NOT_ALLOWED` before any request is made. If a site blocks automation, `emploi.nat.tn` is the documented fallback
for Keejob, or we serve that site from saved snapshots and say so.

## 1.3 Modes

`WEB_MODE` selects the clients. `fake` is fully offline. `replay` serves saved snapshots of real pages with no network.
`live` uses Firecrawl and Browser Use. The deployed demo defaults to replay.
All reported evaluation numbers come from replay or fake runs (Section 4); live runs are reported separately.

## 1.4 Safety at this layer

Every tool result is wrapped as untrusted data with its closing tag escaped. The model sees only validated fields. The
only write target is the sandbox or our own site, and a rejected or timed-out checkpoint means no portal record.
