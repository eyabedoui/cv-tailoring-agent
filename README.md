# CV Tailoring Agent

**CS496 -- AI Engineering \| Project 3: The Operator**

An agentic AI system that helps candidates discover job opportunities,
analyze job requirements, tailor a CV and cover letter, and prepare an
application for submission.

The candidate stays in control throughout the process: **an application
is submitted only after explicit approval through the chat interface.**

------------------------------------------------------------------------

## Project Overview

The agent follows an end-to-end workflow:

1.  **Find jobs** -- searches approved job platforms based on the
    candidate's request.
2.  **Read a posting** -- retrieves and parses the selected job
    description.
3.  **Tailor documents** -- prepares a job-specific CV and cover letter
    using the candidate's master CV and the posting requirements.
4.  **Review** -- presents the generated documents to the candidate.
5.  **Revise or decide** -- allows the candidate to request changes,
    reject the application, or approve it.
6.  **Submit** -- submits the application to the project's own
    application portal only after the candidate clicks the approval
    button.

The chat supports multiple turns and keeps the session state between
messages. A candidate can request up to two revisions. Typing "yes" does
not count as approval.

## Supported Job Platforms

The agent searches and reads job postings from three approved external
platforms:

  ---------------------------------------------------------------------------------------------------
  Platform                Website                                             Job market
  ----------------------- --------------------------------------------------- -----------------------
  Tanitjobs               [tanitjobs.com](https://www.tanitjobs.com/)         Tunisian jobs, mostly
                                                                              French

  Keejob                  [keejob.com](https://www.keejob.com/)               Tunisian jobs in French
                                                                              and English

  We Work Remotely        [weworkremotely.com](https://weworkremotely.com/)   Remote jobs, mainly
                                                                              English
  ---------------------------------------------------------------------------------------------------

Keejob has `emploi.nat.tn` as a fallback if automation is blocked or not
permitted.

**External-site policy:** Real job platforms are read-only. The agent
does not log in, apply, or crawl these websites. LinkedIn and all other
unapproved domains are rejected by the domain allowlist.

### Internal Application Portal

The project includes its own application portal, built with Flask,
containing 25 fictional job postings and dedicated prompt-injection test
postings.

Applications are submitted only to this portal. It is used to test the
complete application workflow safely.

------------------------------------------------------------------------

## Architecture and Technologies

  -----------------------------------------------------------------------
  Component               Technology              Responsibility
  ----------------------- ----------------------- -----------------------
  Agent and orchestration Python                  Manages the agent loop,
                                                  tools, sessions, and
                                                  workflow

  Language model          OpenAI API              Interprets requests and
                                                  coordinates the agent's
                                                  actions

  Chat interface          Chainlit                Provides the
                                                  interactive chat and
                                                  approval checkpoint

  Job search              Browser Use             Searches approved job
                                                  sites

  Job-page extraction     Firecrawl               Retrieves job-page
                                                  content

  Job parsing             Python and              Extracts and validates
                          model-assisted          job requirements
                          extraction              

  Input/output validation Pydantic schemas        Validates tool
                                                  arguments and results

  Application portal      Flask                   Hosts the internal job
                                                  and application portal

  Browser automation      Playwright / Chromium   Supports browser-based
                                                  operations

  Evaluation              Custom Python           Runs scenarios and
                          evaluation runner       measures agent
                                                  performance
  -----------------------------------------------------------------------

### Main Workflow

``` text
Candidate
    |
    v
Chainlit Chat
    |
    v
Agent Session and Orchestration
    |
    +----> Find Jobs (Browser Use)
    |          |
    |          v
    |     Approved Job Sites
    |
    +----> Read Job Posting (Firecrawl)
    |          |
    |          v
    |     Parse Requirements
    |
    +----> Tailor CV and Cover Letter
    |
    v
Candidate Review
    |
    +----> Request Changes (maximum 2 revisions)
    |
    +----> Reject ------> Stop; no application record
    |
    +----> Approve via Button
                 |
                 v
          Internal Flask Portal
                 |
                 v
          Application Submitted
```

------------------------------------------------------------------------

## Safety and Human Approval

Safety is a core part of the project. Job postings, search results, and
other external page content are treated as untrusted data because they
may contain instructions intended to manipulate the agent.

The system includes the following safeguards:

-   **Explicit human approval:** Only the approval button authorizes
    submission. A typed message such as "yes" is not sufficient.
-   **Domain allowlist:** Only approved job domains can be accessed.
    LinkedIn and other unauthorized domains are refused.
-   **Prompt-injection defenses:** Instructions embedded in job pages,
    search results, company fields, and other external content must not
    override the agent's instructions.
-   **Untrusted-content handling:** Tool results are wrapped as
    untrusted data, and closing tags are escaped.
-   **Restricted browser automation:** Browser Use is limited to one
    host per call, with a fresh profile, fixed task instructions, step
    limits, and timeouts. No login or downloads are allowed.
-   **Controlled writes:** File writes are restricted to the sandbox, a
    fixed candidate ID, and the internal application site.
-   **Submission verification:** The portal's saved state is the source
    of truth, not the browser agent's claim that it submitted
    successfully.
-   **Duplicate-submission protection:** The application state is
    checked to prevent repeated submissions.
-   **Execution limits:** The agent has per-turn and session limits,
    repeat-call detection, and checkpoint timeouts.
-   **Controlled retries:** Only errors marked as retryable are retried.
    Blocked or unauthorized sites are never retried.

------------------------------------------------------------------------

## Evaluation and Testing

The project includes automated tests and an evaluation runner to assess
the agent's reliability, safety, and efficiency.

Evaluation covers:

-   Task success and step accuracy.
-   Tool-call precision and wasted steps.
-   Recovery after tool failures.
-   Fabrication detection, including inflated experience levels,
    invented numbers, changed dates, and merged roles.
-   Parser accuracy against manually labeled job requirements.
-   Prompt-injection resistance.
-   Execution limits and stopping behavior.
-   Token usage, service costs, and execution time, including p50 and
    p95 latency.

Test scenarios cover successful applications, no matching jobs, invalid
arguments, unknown tools, empty results, service failures, timeouts,
blocked sites, repeated calls, duplicate submissions, user rejection,
revision requests, and prompt-injection attempts.

### Evaluation Modes

  -----------------------------------------------------------------------
  Mode                                Description
  ----------------------------------- -----------------------------------
  **Offline**                         Uses a fake model and simulated
                                      tools. Does not require API keys or
                                      network access.

  **Replay**                          Uses saved website snapshots with
                                      the real model, without live
                                      website access.

  **Live**                            Uses the real model and approved
                                      external services.
  -----------------------------------------------------------------------

Replay mode makes it possible to reproduce tests using captured pages
without repeatedly accessing external websites.

------------------------------------------------------------------------

## Getting Started

### Requirements

-   Python
-   Git
-   API keys for live model and scraping operations
-   Chromium installed through the project setup for browser-based
    operations

### 1. Clone the repository

``` bash
git clone <repository-url>
cd CV-Tailoring-Agent
```

### 2. Install dependencies and initialize the sandbox

``` bash
pip install -r requirements.txt
python -m sandbox setup
python -m sandbox seed
```

The setup command installs the browser requirements. The seed command
initializes the local sandbox with its fictional job postings.

### 3. Configure environment variables

Create a local `.env` file from the example:

``` bash
cp .env.example .env
```

Add the required keys:

``` env
OPENAI_API_KEY=your_openai_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
```

  Key                   Required for
  --------------------- -------------------------------------------------
  `OPENAI_API_KEY`      Real model runs and live Browser Use operations
  `FIRECRAWL_API_KEY`   Live job-page scraping and snapshot creation

Get an OpenAI API key from
[platform.openai.com](https://platform.openai.com/) and a Firecrawl API
key from [firecrawl.dev](https://www.firecrawl.dev/).

Keep `.env` local. Never commit API keys, credentials, logs, or real
personal data.

### 4. Start the chat

Run the interactive agent:

``` bash
python -m agent chat
```

For an offline demonstration without API keys:

``` bash
python -m agent --model fake --auto-approve
```

Use the help command to see the available options:

``` bash
python -m agent --help
```

------------------------------------------------------------------------

## Replay Mode

Replay mode runs the agent using previously captured website snapshots.
It is useful for offline evaluation and reproducible testing.

Capture a page snapshot (requires a Firecrawl API key):

``` bash
python -m sandbox snapshot <job-url>
```

Set replay mode:

**Windows Command Prompt**

``` bat
set WEB_MODE=replay
```

**macOS / Linux**

``` bash
export WEB_MODE=replay
```

Then run the agent against the saved snapshot:

``` bash
python -m agent --job-url <job-url>
```

Replay mode uses saved content and does not need live access to the job
website.

------------------------------------------------------------------------

## Running Tests and Evaluation

Run the automated test suite:

``` bash
python -m pytest -q
```

Run the offline evaluation:

``` bash
python -m eval.runner --model fake
```

Run the credential scan:

``` bash
python scripts/scan_secrets.py
```

------------------------------------------------------------------------

## Resetting the Sandbox

Clear generated output and state while keeping the job postings:

``` bash
python -m sandbox reset
```

Seed the sandbox again:

``` bash
python -m sandbox seed
```

------------------------------------------------------------------------

## Deployment

The planned deployment uses:

-   **Chainlit** for the public chat interface.
-   **Flask** for the internal application portal, running in the same
    container at `127.0.0.1:5000`.
-   **GitHub Pages** for the exported static job postings, which allow
    the cloud-based scraper to access postings that would not be
    reachable on localhost.

The hosted chat must be password-protected. Replay mode is the default
deployment mode; live mode is enabled only for demonstrations and graded
runs. API keys are configured through the hosting provider's environment
settings and must never be committed to the repository.

The public deployment URL and login instructions should be added here
once deployment is complete.

------------------------------------------------------------------------

## Project Structure

``` text
CV-Tailoring-Agent/
│
├── agent/              # Agent loop, sessions, prompts and chat workflow
├── clients/            # External service clients
├── eval/               # Evaluation scenarios, metrics and results
├── sandbox/            # Flask portal, job postings and snapshots
├── tests/              # Automated tests
├── docs/               # Project and security documentation
├── scripts/            # Utility and security scripts
│
├── requirements.txt
├── .env.example
├── README.md
└── problems.md
```

*This is a high-level overview; the exact repository structure may
evolve during development.*

------------------------------------------------------------------------

## Project Status

The Week 1 implementation includes:

-   End-to-end agent workflow through the chat interface.
-   Session history and state management across turns.
-   Button-based human approval checkpoint.
-   Integration with the three approved job platforms.
-   Internal Flask application portal with 25 fictional postings and
    prompt-injection test postings.
-   Browser-based job search and application submission to the internal
    portal.
-   Firecrawl-based job-page extraction and replay snapshots.
-   Offline evaluation framework and initial scenarios.
-   Security controls, domain allowlisting, and error handling.

**Testing note:** The project plan records 596 offline tests passing at
the last full run before the additional Week 2 work. The initial offline
evaluation scenarios also passed. Final live evaluation, deployment, and
updated results should be reported after those stages are completed.

------------------------------------------------------------------------

## Team Contributions

  -----------------------------------------------------------------------
  Member                              Responsibilities
  ----------------------------------- -----------------------------------
  **Asma Gannar**                     Live setup, reliability, retries,
                                      execution limits, and optimization

  **Eya Bedoui**                      Agent core, chat interface, web
                                      integration, and sandbox

  **Asma Aouiti**                     Evaluation metrics, scenarios, cost
                                      analysis, and injection testing

  **Nouha Aouiti**                    Security documentation, deployment,
                                      final report, and demonstration
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## Project Documentation

Additional project details are maintained in the `docs/` directory,
including:

-   Approved websites and access restrictions.
-   Human approval process.
-   Sandbox and replay instructions.
-   Error taxonomy.
-   Threat model and security considerations.
-   Deployment instructions.
-   Evaluation metrics and cost model.

------------------------------------------------------------------------

**Course:** CS496 -- AI Engineering\
**Project:** Project 3 -- The Operator\
**Institution:** South Mediterranean University (SMU)
