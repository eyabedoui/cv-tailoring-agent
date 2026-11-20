Subject: CS496 Project 3 — approval for our CV-tailoring agent

Dear Professor,

Group members: Persons A, B, C, and D.  Topic: a CV-tailoring agent.

**What it does.**
The agent reads a job posting and a master CV, writes a tailored CV and cover letter using only
facts from the master CV (no fabrication), then waits for the user to click **Approve** in the
Chainlit chat window before it submits.

**External services used.**
- Job search and reading: Firecrawl (HTML→markdown) and Browser Use (headless Chromium + OpenAI).
  Three allowed sites: tanitjobs.com, keejob.com, weworkremotely.com — read-only, no login.
  LinkedIn is explicitly excluded from the allowlist; the agent returns SITE_NOT_ALLOWED if asked.
- Submission target: our own Flask apply site at 127.0.0.1 — never any real job board.
- Chat UI: Chainlit.
- Language model: OpenAI (gpt-4o-mini by default; model is configurable via CV_AGENT_MODEL).

**Human gate.**
Every submission requires an explicit button click on the Approve page in the UI.
No text message in the chat can trigger a submission; that path is tested and blocked.

**Questions for you.**
1. Which OpenAI model(s) and API base URL should we target for grading?

2. We have received an OpenAI API key. Will a FIRECRAWL_API_KEY also be
   supplied for grading, or should we prepare a replay-mode demo that
   requires no external API keys?
3. What is the per-group spending budget for live API calls?
4. May we publish our static job-posting site on GitHub Pages for the demo?

Best regards,
Nouha (Person D) on behalf of the group

5. We checked the robots.txt files and Terms of Service for Tanitjobs,
   Keejob, and We Work Remotely. Public job pages are generally accessible,
   but we could not confirm explicit permission for automated extraction.
   Should we use these websites only if we obtain authorization, and
   otherwise demonstrate the workflow using our own sandbox and saved
   snapshots?