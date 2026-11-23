
"""
Chainlit UI for the CV-tailoring agent.

Run:
    python -m chainlit run ui/app.py

Models:
    CV_AGENT_MODEL=fake
    CV_AGENT_MODEL=openai
    CV_AGENT_MODEL=groq
"""

import asyncio
import concurrent.futures
import contextvars
import os
from pathlib import Path

import chainlit as cl

from agent.chat_checkpoint import ChatCheckpoint
from agent.config import CHECKPOINT_TIMEOUT_SECONDS
from agent.cv_upload import (
    CvUploadError,
    delete_session_cv,
    save_session_cv,
)
from agent.logger import AgentLogger
from agent.session import Session
from agent.tools.reads import (
    CV_PATH_OVERRIDE,
    JOB_POSTING_OVERRIDE,
)
from ui.logic import (
    APPROVAL_PENDING_REPLY,
    check_credentials,
    format_status_line,
    format_stop_message,
    get_output_files,
    map_tool_error,
    parse_slash_command,
    render_untrusted,
)


# ============================================================
# Welcome
# ============================================================

_WELCOME = """
Welcome! I'm your **CV-tailoring agent**.

**What I can do:**
- Search Keejob for job opportunities
- Read selected job postings using Firecrawl
- Read your uploaded CV
- Compare your skills with job requirements
- Generate a tailored CV using Groq
- Generate a personalized cover letter using Groq
- Submit an application only after your approval

**Commands:**
- `/jobs Python` — Search Keejob and select a job
- `/match` — Compare your CV with the selected job
- `/generate cv` — Generate a tailored CV draft
- `/generate letter` — Generate a cover letter draft
- `/new` — Start a new task
- `/status` — Show session status
- `/files` — Show generated files

Upload your CV as a `.md` or `.txt` file.

**Important:** Generating documents does not submit an application.
Any submission requires a separate explicit approval.
"""


# ============================================================
# Model selection
# ============================================================

def _fake_model():
    from agent.demo_model import DemoModel
    return DemoModel()


def _build_model():

    model_name = os.environ.get(
        "CV_AGENT_MODEL", "fake"
    ).strip().lower()

    if model_name == "groq":

        try:
            from agent.budget import BudgetTracker
            from agent.groq_model import GroqModel

            if not os.environ.get("GROQ_API_KEY"):
                return (
                    _fake_model(),
                    "GROQ_API_KEY is missing. "
                    "Using demonstration mode.",
                )

            budget_limit = float(
                os.environ.get(
                    "GROQ_API_BUDGET_USD", "0"
                )
            )

            if budget_limit <= 0:
                return (
                    _fake_model(),
                    "Groq budget must be greater than zero. "
                    "Using demonstration mode.",
                )

            budget = BudgetTracker(
                limit_usd=budget_limit
            )

            return GroqModel(budget=budget), None

        except Exception as exc:
            return (
                _fake_model(),
                f"Groq initialization failed: {exc}. "
                "Using demonstration mode.",
            )

    if model_name == "openai":

        if not os.environ.get("OPENAI_API_KEY"):
            return (
                _fake_model(),
                "OpenAI key missing. "
                "Using demonstration mode.",
            )

        try:
            from agent.model import OpenAIModel
            return OpenAIModel(), None

        except Exception as exc:
            return (
                _fake_model(),
                f"OpenAI unavailable: {exc}. "
                "Using demonstration mode.",
            )

    return _fake_model(), None


# ============================================================
# Authentication
# ============================================================

if (
    os.environ.get("APP_USERNAME")
    and os.environ.get("APP_PASSWORD")
):

    @cl.password_auth_callback
    def auth_callback(username: str, password: str):

        valid = check_credentials(
            username,
            password,
            os.environ.get("APP_USERNAME"),
            os.environ.get("APP_PASSWORD"),
        )

        if valid:
            return cl.User(
                identifier=username,
                metadata={"role": "candidate"},
            )

        return None


# ============================================================
# Chat initialization
# ============================================================

@cl.on_chat_start
async def on_chat_start():

    model, warning = _build_model()

    # Reuse the existing model for document generation.
    cl.user_session.set("generation_model", model)

    if warning:
        await cl.Message(
            content=f"⚠️ {warning}"
        ).send()

    loop = asyncio.get_running_loop()
    ctx_holder = {"ctx": None}

    cl.user_session.set("ctx_holder", ctx_holder)
    cl.user_session.set("approval_pending", False)
    cl.user_session.set("approval_msg", None)

    cl.user_session.set("selected_job", None)
    cl.user_session.set("selected_job_description", None)
    cl.user_session.set("selected_job_markdown", None)
    cl.user_session.set("cv_path", None)

    cl.user_session.set("generated_cv", None)
    cl.user_session.set("generated_cover_letter", None)

    # --------------------------------------------------------
    # Human approval callback
    # --------------------------------------------------------

    def present_fn(review_text: str) -> None:

        ctx = ctx_holder.get("ctx")
        done = concurrent.futures.Future()

        async def _post():

            cl.user_session.set(
                "approval_pending", True
            )

            done.set_result(None)

            try:
                approved = await _ask_approval(
                    review_text
                )
            except Exception:
                approved = False
            finally:
                cl.user_session.set(
                    "approval_pending", False
                )

            if approved:
                await cl.Message(
                    content="✅ **Approved.** Submitting…"
                ).send()
            else:
                await cl.Message(
                    content=(
                        "❌ **Not approved.** "
                        "Submission cancelled."
                    )
                ).send()

            checkpoint.submit_decision(approved)

        if ctx is not None:

            loop.call_soon_threadsafe(
                lambda: loop.create_task(
                    _post(),
                    context=ctx,
                )
            )

        else:

            asyncio.run_coroutine_threadsafe(
                _post(),
                loop,
            )

        done.result(timeout=30)

    checkpoint = ChatCheckpoint(
        present_fn=present_fn,
        timeout_seconds=CHECKPOINT_TIMEOUT_SECONDS,
    )

    session = Session(
        model=model,
        checkpoint=checkpoint,
        logger=AgentLogger(),
    )

    cl.user_session.set("session", session)
    cl.user_session.set("checkpoint", checkpoint)
    cl.user_session.set("loop", loop)

    await cl.Message(
        content=_WELCOME
    ).send()


# ============================================================
# Chat cleanup
# ============================================================

@cl.on_chat_end
async def on_chat_end():

    checkpoint = cl.user_session.get("checkpoint")
    pending = cl.user_session.get(
        "approval_pending", False
    )

    if checkpoint and pending:
        cl.user_session.set(
            "approval_pending", False
        )
        checkpoint.submit_decision(False)

    session_id = cl.user_session.get("id")

    if session_id:
        delete_session_cv(session_id)


# ============================================================
# Approval dialog
# ============================================================

async def _ask_approval(review_text: str) -> bool:

    safe_review = render_untrusted(
        review_text,
        max_chars=2000,
    )

    response = await cl.AskActionMessage(
        content=(
            "**Application Review**\n\n"
            + safe_review
            + "\n\n"
            "Use the buttons below to approve "
            "or reject this submission."
        ),
        actions=[
            cl.Action(
                name="ask_approve",
                payload={"value": "approve"},
                label="✅ Approve",
            ),
            cl.Action(
                name="ask_reject",
                payload={"value": "reject"},
                label="❌ Reject",
            ),
        ],
        timeout=int(CHECKPOINT_TIMEOUT_SECONDS) + 5,
        raise_on_timeout=False,
    ).send()

    return (
        bool(response)
        and response.get("name") == "ask_approve"
    )


# ============================================================
# Keejob search and Firecrawl extraction
# ============================================================

async def _handle_job_search(query: str) -> None:

    if cl.user_session.get(
        "approval_pending", False
    ):
        await cl.Message(
            content=APPROVAL_PENDING_REPLY
        ).send()
        return

    query = query.strip()

    if not query or len(query) > 200:
        await cl.Message(
            content="Use `/jobs Python` to search for jobs."
        ).send()
        return

    from agent.tools.search import find_jobs
    from agent.tools.keejob_client import search_keejob

    class _KeejobDiscoveryClient:

        def search(
            self,
            query: str,
            site: str,
        ) -> list[dict]:

            if site != "keejob":
                return []

            return search_keejob(
                query=query,
                max_results=5,
            )

    await cl.Message(
        content=f"🔎 Searching Keejob for **{query}**..."
    ).send()

    try:
        result = await asyncio.to_thread(
            find_jobs,
            query,
            "keejob",
            _client=_KeejobDiscoveryClient(),
        )

    except Exception as exc:
        await cl.Message(
            content=f"Job discovery failed: {exc}"
        ).send()
        return

    if "error" in result:
        await cl.Message(
            content=(
                "Job discovery failed: "
                + str(
                    result.get(
                        "message", "Unknown error"
                    )
                )
            )
        ).send()
        return

    jobs = result.get("jobs", [])[:5]

    if not jobs:
        await cl.Message(
            content="No jobs found. Try another keyword."
        ).send()
        return

    # --------------------------------------------------------
    # Display results
    # --------------------------------------------------------

    lines = ["## Keejob job results", ""]

    for index, job in enumerate(jobs, 1):
        lines.extend([
            f"**{index}. {job['title']}**",
            f"Company: {job['company']}",
            f"Location: {job['location']}",
            f"URL: {job['url']}",
            "",
        ])

    await cl.Message(
        content="\n".join(lines)
    ).send()

    # --------------------------------------------------------
    # Job selection
    # --------------------------------------------------------

    actions = [
        cl.Action(
            name="select_job",
            payload={"job_id": job["job_id"]},
            label=f"Select job {index}",
        )
        for index, job in enumerate(jobs, 1)
    ]

    actions.append(
        cl.Action(
            name="cancel_job_selection",
            payload={},
            label="Cancel",
        )
    )

    selection = await cl.AskActionMessage(
        content="**Which job would you like to select?**",
        actions=actions,
        timeout=180,
        raise_on_timeout=False,
    ).send()

    if (
        not selection
        or selection.get("name") != "select_job"
    ):
        await cl.Message(
            content="Job selection cancelled."
        ).send()
        return

    selected_id = selection.get(
        "payload", {}
    ).get("job_id")

    selected_job = next(
        (
            job for job in jobs
            if job["job_id"] == selected_id
        ),
        None,
    )

    if selected_job is None:
        await cl.Message(
            content="Invalid job selection."
        ).send()
        return

    from agent.sites import url_belongs_to_site

    if not url_belongs_to_site(
        selected_job["url"],
        "keejob",
    ):
        await cl.Message(
            content="Invalid or unauthorized job URL."
        ).send()
        return

    cl.user_session.set(
        "selected_job", selected_job
    )
    cl.user_session.set(
        "selected_job_description", None
    )
    cl.user_session.set(
        "selected_job_markdown", None
    )

    # Clear stale document references when changing jobs.
    cl.user_session.set("generated_cv", None)
    cl.user_session.set("generated_cover_letter", None)

    await cl.Message(
        content=(
            f"✅ **Selected job:** {selected_job['title']}\n\n"
            f"**Company:** {selected_job['company']}\n\n"
            f"**URL:** {selected_job['url']}\n\n"
            "Extracting the description with Firecrawl..."
        )
    ).send()

    # --------------------------------------------------------
    # Firecrawl extraction
    # --------------------------------------------------------

    from agent.tools.clients import FirecrawlPostingClient

    try:
        extraction = await asyncio.to_thread(
            FirecrawlPostingClient().fetch,
            selected_job["url"],
        )

    except Exception as exc:
        await cl.Message(
            content=f"Firecrawl extraction failed: {exc}"
        ).send()
        return

    if "error" in extraction:
        await cl.Message(
            content=(
                "Firecrawl extraction failed: "
                + str(
                    extraction.get(
                        "message", "Unknown error"
                    )
                )
            )
        ).send()
        return

    markdown = extraction.get("markdown", "")

    if not isinstance(markdown, str):
        markdown = ""

    marker = "## Description de l'annonce"

    if marker not in markdown:
        await cl.Message(
            content=(
                "Firecrawl returned content, but the "
                "job description section was not found."
            )
        ).send()
        return

    job_description = markdown.split(
        marker, 1
    )[1]

    job_description = job_description.split(
        "\nPartager", 1
    )[0].strip()

    if not job_description:
        await cl.Message(
            content="The extracted job description is empty."
        ).send()
        return

    cl.user_session.set(
        "selected_job_description",
        job_description,
    )
    cl.user_session.set(
        "selected_job_markdown",
        markdown,
    )

    await cl.Message(
        content=(
            "✅ **Firecrawl extraction successful!**\n\n"
            f"### {selected_job['title']}\n\n"
            f"**Company:** {selected_job['company']}\n\n"
            f"**Job ID:** {selected_job['job_id']}\n\n"
            "### Job description\n\n"
            f"{job_description[:5000]}\n\n"
            "---\n\n"
            "The selected job description is ready "
            "for CV matching and tailoring.\n\n"
            "Type `/match` after uploading your CV.\n\n"
            "**No application has been submitted.**"
        )
    ).send()


# ============================================================
# Direct CV-to-job matching (NO GROQ)
# ============================================================

async def _handle_skill_match() -> None:

    if cl.user_session.get(
        "approval_pending", False
    ):
        await cl.Message(
            content=APPROVAL_PENDING_REPLY
        ).send()
        return

    selected_job = cl.user_session.get("selected_job")
    markdown = cl.user_session.get(
        "selected_job_markdown"
    )
    cv_path = cl.user_session.get("cv_path")

    if (
        not isinstance(selected_job, dict)
        or not isinstance(markdown, str)
        or not markdown.strip()
    ):
        await cl.Message(
            content="Select a job first using `/jobs Python`."
        ).send()
        return

    if not cv_path:
        await cl.Message(
            content=(
                "Upload your `.md` or `.txt` CV first. "
                "Attach the actual file, not only its name."
            )
        ).send()
        return

    from agent.sites import url_belongs_to_site
    from agent.tools.reads import (
        read_job_posting,
        read_master_cv,
        match_skills,
    )

    url = selected_job.get("url", "")

    if not url_belongs_to_site(url, "keejob"):
        await cl.Message(
            content="The selected job URL is not authorized."
        ).send()
        return

    def run_matching():

        cv_token = CV_PATH_OVERRIDE.set(
            Path(cv_path)
        )

        job_token = JOB_POSTING_OVERRIDE.set(
            (url, markdown)
        )

        try:
            job = read_job_posting(url)

            if not isinstance(job, dict):
                return {
                    "error": "Invalid job posting response."
                }

            if "error" in job:
                return {"error": f"Job: {job}"}

            cv = read_master_cv()

            if not isinstance(cv, dict):
                return {"error": "Invalid CV response."}

            if "error" in cv:
                return {"error": f"CV: {cv}"}

            if not job.get("requirements"):
                return {
                    "error": "No job requirements were extracted."
                }

            if not isinstance(cv.get("text"), str):
                return {
                    "error": "CV text could not be read."
                }

            matching = match_skills(
                cv["text"], job
            )

            if not isinstance(matching, dict):
                return {
                    "error": "Invalid matching response."
                }

            if "error" in matching:
                return {
                    "error": f"Matching: {matching}"
                }

            return {
                "job": job,
                "matching": matching,
            }

        finally:
            JOB_POSTING_OVERRIDE.reset(job_token)
            CV_PATH_OVERRIDE.reset(cv_token)

    try:
        result = await asyncio.to_thread(
            run_matching
        )

    except Exception as exc:
        await cl.Message(
            content=(
                "Matching failed: "
                f"{type(exc).__name__}: {exc}"
            )
        ).send()
        return

    if "error" in result:
        await cl.Message(
            content=f"Matching failed: {result['error']}"
        ).send()
        return

    job = result["job"]
    matching = result["matching"]

    matched = matching.get("matched", [])
    missing = matching.get("missing", [])
    score = matching.get("score")

    if not isinstance(matched, list):
        matched = []

    if not isinstance(missing, list):
        missing = []

    score_text = (
        f"{score:.1%}"
        if isinstance(score, (int, float))
        else "Not available"
    )

    matched_text = (
        "\n".join(
            f"- {skill}" for skill in matched
        )
        if matched else "- None"
    )

    missing_text = (
        "\n".join(
            f"- {skill}" for skill in missing
        )
        if missing else "- None"
    )

    await cl.Message(
        content=(
            "## CV–Job Matching Results\n\n"
            f"**Job:** {job.get('title', selected_job.get('title', ''))}\n\n"
            f"**Company:** {job.get('company', selected_job.get('company', ''))}\n\n"
            f"**Match score:** {score_text}\n\n"
            "### Matching skills\n\n"
            f"{matched_text}\n\n"
            "### Missing skills\n\n"
            f"{missing_text}\n\n"
            "**No documents generated or applications submitted.**"
        )
    ).send()


# ============================================================
# NEW: Groq document generation
# ============================================================

async def _handle_generate(kind: str) -> None:
    """
    Generate and save one draft document.

    Supported:
        /generate cv
        /generate letter

    This function does NOT submit an application.
    """

    if cl.user_session.get(
        "approval_pending", False
    ):
        await cl.Message(
            content=APPROVAL_PENDING_REPLY
        ).send()
        return

    kind = kind.strip().lower()

    if kind == "letter":
        kind = "cover_letter"

    if kind not in ("cv", "cover_letter"):
        await cl.Message(
            content=(
                "Use `/generate cv` or `/generate letter`."
            )
        ).send()
        return

    if os.environ.get(
        "CV_AGENT_MODEL", "fake"
    ).strip().lower() != "groq":
        await cl.Message(
            content=(
                "Document generation requires Groq mode."
            )
        ).send()
        return

    selected_job = cl.user_session.get(
        "selected_job"
    )

    markdown = cl.user_session.get(
        "selected_job_markdown"
    )

    cv_path = cl.user_session.get("cv_path")

    model = cl.user_session.get(
        "generation_model"
    )

    if (
        not isinstance(selected_job, dict)
        or not isinstance(markdown, str)
        or not markdown.strip()
    ):
        await cl.Message(
            content=(
                "Select a job first using `/jobs Python`."
            )
        ).send()
        return

    if not cv_path:
        await cl.Message(
            content=(
                "Upload your CV before generating documents."
            )
        ).send()
        return

    from agent.groq_model import GroqModel
    from agent.sites import url_belongs_to_site

    if not isinstance(model, GroqModel):
        await cl.Message(
            content=(
                "Groq is not initialized. "
                "Check the API key and budget configuration."
            )
        ).send()
        return

    job_url = selected_job.get("url", "")

    if not url_belongs_to_site(
        job_url, "keejob"
    ):
        await cl.Message(
            content="Selected job URL is not authorized."
        ).send()
        return

    job_id = str(
        selected_job.get("job_id", "")
    )

    from agent.document_generator import generate_document

    document_name = (
        "tailored CV"
        if kind == "cv"
        else "cover letter"
    )

    await cl.Message(
        content=(
            f"Generating a {document_name} draft for "
            f"**{selected_job.get('company', '')}**.\n\n"
            "The document will be saved for review only."
        )
    ).send()

    # --------------------------------------------------------
    # Run generation with uploaded CV and selected posting
    # --------------------------------------------------------

    def run_generation():

        cv_token = CV_PATH_OVERRIDE.set(
            Path(cv_path)
        )

        job_token = JOB_POSTING_OVERRIDE.set(
            (job_url, markdown)
        )

        try:
            return generate_document(
                model=model,
                job_url=job_url,
                job_id=job_id,
                kind=kind,
            )

        finally:
            JOB_POSTING_OVERRIDE.reset(job_token)
            CV_PATH_OVERRIDE.reset(cv_token)

    try:
        result = await asyncio.to_thread(
            run_generation
        )

    except Exception as exc:
        await cl.Message(
            content=(
                "Generation failed: "
                f"{type(exc).__name__}: {exc}"
            )
        ).send()
        return

    if not isinstance(result, dict):
        await cl.Message(
            content="Generation failed: Invalid result."
        ).send()
        return

    if "error" in result:
        await cl.Message(
            content=(
                f"Generation failed: {result['error']}"
            )
        ).send()
        return

    # --------------------------------------------------------
    # Store generated document reference
    # --------------------------------------------------------

    cl.user_session.set(
        f"generated_{kind}",
        result.get("path"),
    )

    # --------------------------------------------------------
    # Display generated document
    # --------------------------------------------------------

    await cl.Message(
        content=(
            f"## Generated {document_name.title()}\n\n"
            f"{result.get('text', '')}\n\n"
            "---\n\n"
            f"**Saved:** `{result.get('path', '')}`\n\n"
            "**Draft only — not submitted.**\n\n"
            "Review the document carefully to verify "
            "that every skill, qualification, and "
            "experience is accurate."
        )
    ).send()


# ============================================================
# Main Chainlit message handler
# ============================================================

@cl.on_message
async def on_message(message: cl.Message):

    text = (message.content or "").strip()

    # --------------------------------------------------------
    # 1. Keejob search
    # --------------------------------------------------------

    if text == "/jobs" or text.startswith("/jobs "):
        await _handle_job_search(text[5:])
        return

    # --------------------------------------------------------
    # 2. Generic slash commands
    #
    # IMPORTANT:
    # /match and /generate must bypass this handler.
    # --------------------------------------------------------

    command, args = parse_slash_command(text)

    if command and command not in (
        "match",
        "generate",
    ):
        await _handle_slash(command, args)
        return

    # --------------------------------------------------------
    # 3. Prevent text-based approval
    # --------------------------------------------------------

    if cl.user_session.get(
        "approval_pending", False
    ):
        await cl.Message(
            content=APPROVAL_PENDING_REPLY
        ).send()
        return

    # --------------------------------------------------------
    # 4. Process uploaded CV files FIRST
    # --------------------------------------------------------

    uploaded = [
        element
        for element in (message.elements or [])
        if getattr(element, "path", None)
    ]

    if uploaded:

        try:
            with open(
                uploaded[0].path, "rb"
            ) as file:
                data = file.read()

            cv_path = save_session_cv(
                cl.user_session.get("id"),
                uploaded[0].name,
                data,
            )

            cl.user_session.set(
                "cv_path", str(cv_path)
            )

            # Clear document references when the CV changes.
            cl.user_session.set("generated_cv", None)
            cl.user_session.set(
                "generated_cover_letter", None
            )

            await cl.Message(
                content=(
                    f"✅ CV `{uploaded[0].name}` received. "
                    "I will use it as your master CV "
                    "in this chat only."
                )
            ).send()

        except CvUploadError as exc:
            await cl.Message(
                content=f"⚠️ CV not used: {exc}"
            ).send()
            return

        if not text:
            return

    # --------------------------------------------------------
    # 5. Match skills after CV upload
    # --------------------------------------------------------

    if text == "/match":
        await _handle_skill_match()
        return

    # --------------------------------------------------------
    # 6. Generate documents after CV upload
    # --------------------------------------------------------

    if text == "/generate" or text.startswith(
        "/generate "
    ):
        kind = text[len("/generate"):].strip()
        await _handle_generate(kind)
        return

    # --------------------------------------------------------
    # 7. Normal Groq / ReAct workflow
    # --------------------------------------------------------

    session: Session = cl.user_session.get(
        "session"
    )

    loop = cl.user_session.get("loop")

    ctx_holder = cl.user_session.get(
        "ctx_holder"
    )

    ctx_holder["ctx"] = contextvars.copy_context()

    step_queue = asyncio.Queue()

    def on_step_fn(event: dict) -> None:
        loop.call_soon_threadsafe(
            step_queue.put_nowait,
            event,
        )

    session._on_step = on_step_fn

    cv_override = cl.user_session.get("cv_path")

    selected_job = cl.user_session.get(
        "selected_job"
    )

    selected_markdown = cl.user_session.get(
        "selected_job_markdown"
    )

    has_selected_job = (
        isinstance(selected_job, dict)
        and isinstance(
            selected_job.get("url"), str
        )
        and isinstance(
            selected_markdown, str
        )
        and bool(selected_markdown.strip())
    )

    print("\n===== CHAINLIT JOB DEBUG =====")
    print(
        "Selected job:",
        selected_job.get("title")
        if isinstance(selected_job, dict)
        else None,
    )
    print(
        "Markdown available:",
        has_selected_job,
    )
    print("=============================\n")

    send_ctx = contextvars.copy_context()

    # --------------------------------------------------------
    # Worker context
    # --------------------------------------------------------

    def run_agent():

        cv_token = CV_PATH_OVERRIDE.set(
            Path(cv_override)
            if cv_override
            else None
        )

        job_token = JOB_POSTING_OVERRIDE.set(
            (
                selected_job["url"],
                selected_markdown,
            )
            if has_selected_job
            else None
        )

        try:
            agent_text = text

            if has_selected_job:

                selected_title = selected_job.get(
                    "title", ""
                )

                selected_company = selected_job.get(
                    "company", ""
                )

                selected_url = selected_job["url"]

                agent_text = (
                    "CURRENT SELECTED JOB "
                    "(verified by the application UI):\n"
                    f"Title: {selected_title}\n"
                    f"Company: {selected_company}\n"
                    f"URL: {selected_url}\n\n"
                    "The candidate already selected this "
                    "specific job in the interface.\n"
                    "Use read_job_posting with the exact "
                    "selected URL above.\n"
                    "Do not call find_jobs unless the "
                    "candidate explicitly asks for a new search.\n"
                    "Use read_master_cv for the uploaded CV.\n"
                    "For skill comparison, use match_skills "
                    "with actual tool results.\n"
                    "Do not invent skills or experience.\n"
                    "If analysis only is requested, do not "
                    "generate documents or submit an "
                    "application.\n\n"
                    "CANDIDATE REQUEST:\n"
                    f"{text}"
                )

            return session.send(agent_text)

        finally:
            JOB_POSTING_OVERRIDE.reset(job_token)
            CV_PATH_OVERRIDE.reset(cv_token)

    send_task = loop.run_in_executor(
        None,
        send_ctx.run,
        run_agent,
    )

    # --------------------------------------------------------
    # Display agent tool calls
    # --------------------------------------------------------

    while not send_task.done():

        try:
            event = await asyncio.wait_for(
                step_queue.get(),
                timeout=0.1,
            )

            await _display_step(event)

        except asyncio.TimeoutError:
            pass

    while not step_queue.empty():

        try:
            event = step_queue.get_nowait()
            await _display_step(event)

        except asyncio.QueueEmpty:
            break

    # --------------------------------------------------------
    # Final agent result
    # --------------------------------------------------------

    try:
        result = send_task.result()

    except Exception as exc:
        await cl.Message(
            content=(
                "Unexpected error: "
                f"{type(exc).__name__}: {exc}"
            )
        ).send()
        return

    await _handle_result(result, session)


# ============================================================
# Display tool step
# ============================================================

async def _display_step(event: dict) -> None:

    tool = event.get("tool", "(unknown)")

    args_summary = str(
        event.get("arguments", {})
    )[:200]

    result = event.get("result", {})

    if (
        isinstance(result, dict)
        and "error" in result
    ):
        result_summary = map_tool_error(
            result.get("error", ""),
            result.get("message", ""),
            result.get("retryable", False),
        )[:200]

    else:
        result_summary = str(result)[:200]

    async with cl.Step(name=tool) as step:
        step.input = args_summary
        step.output = result_summary


# ============================================================
# Final result
# ============================================================

async def _handle_result(
    result: dict,
    session: Session,
) -> None:

    cl.user_session.set(
        "approval_pending", False
    )

    stop_reason = result.get(
        "stop_reason", ""
    )

    answer = result.get("answer") or ""

    special = format_stop_message(
        stop_reason,
        answer,
    )

    if special:
        await cl.Message(
            content=special
        ).send()
        return

    if answer:
        await cl.Message(
            content=answer
        ).send()

    status = format_status_line(
        total_steps=session._total_steps,
        total_cost_usd=0.0,
        stop_reason=(
            stop_reason
            if stop_reason not in ("done", "")
            else None
        ),
    )

    await cl.Message(
        content=f"_{status}_"
    ).send()


# ============================================================
# Slash commands
# ============================================================

async def _handle_slash(
    command: str,
    args: str,
) -> None:

    session: Session = cl.user_session.get(
        "session"
    )

    # --------------------------------------------------------
    # /new
    # --------------------------------------------------------

    if command == "new":

        model, warning = _build_model()

        # Update the generation model after a reset.
        cl.user_session.set(
            "generation_model", model
        )

        new_session = Session(
            model=model,
            checkpoint=cl.user_session.get(
                "checkpoint"
            ),
            logger=AgentLogger(),
        )

        cl.user_session.set(
            "session", new_session
        )

        cl.user_session.set(
            "selected_job", None
        )
        cl.user_session.set(
            "selected_job_description", None
        )
        cl.user_session.set(
            "selected_job_markdown", None
        )
        cl.user_session.set(
            "generated_cv", None
        )
        cl.user_session.set(
            "generated_cover_letter", None
        )
        cl.user_session.set(
            "approval_pending", False
        )

        if warning:
            await cl.Message(
                content=f"⚠️ {warning}"
            ).send()

        await cl.Message(
            content="✨ Session reset. Start a new task!"
        ).send()

    # --------------------------------------------------------
    # /status
    # --------------------------------------------------------

    elif command == "status":

        job_id = None

        workflow_state = session._workflow_state

        if (
            workflow_state
            and isinstance(
                workflow_state.get("job"),
                dict,
            )
        ):
            job_id = workflow_state[
                "job"
            ].get("job_id")

        selected_job = cl.user_session.get(
            "selected_job"
        )

        selected_title = (
            selected_job.get("title", "none")
            if isinstance(selected_job, dict)
            else "none"
        )

        cv_path = cl.user_session.get("cv_path")

        status = format_status_line(
            total_steps=session._total_steps,
            total_cost_usd=0.0,
        )

        await cl.Message(
            content=(
                f"{status}\n\n"
                f"Workflow job: **{job_id or 'none'}**\n\n"
                f"Selected Keejob job: **{selected_title}**\n\n"
                f"CV uploaded: **{'Yes' if cv_path else 'No'}**"
            )
        ).send()

    # --------------------------------------------------------
    # /files
    # --------------------------------------------------------

    elif command == "files":

        files = get_output_files()

        if files:

            names = "\n".join(
                f"- `{filename}`"
                for filename in files
            )

            await cl.Message(
                content="Generated files:\n" + names
            ).send()

        else:

            await cl.Message(
                content="No generated files found yet."
            ).send()

    # --------------------------------------------------------
    # Unknown command
    # --------------------------------------------------------

    else:

        await cl.Message(
            content=(
                f"Unknown command: `/{command}`.\n"
                "Try `/new`, `/status`, `/files`, "
                "`/jobs Python`, `/match`, "
                "`/generate cv`, or `/generate letter`."
            )
        ).send()
