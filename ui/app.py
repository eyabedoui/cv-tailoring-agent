"""
Chainlit UI for the CV-tailoring agent.

Run with:  chainlit run ui/app.py

Model selection via CV_AGENT_MODEL env var:
  "fake"   — scripted walkthrough, no API key required (default)
  "openai" — real OpenAI model, requires OPENAI_API_KEY
"""

import asyncio
import concurrent.futures
import contextvars
import os

import chainlit as cl

from agent.chat_checkpoint import ChatCheckpoint
from agent.config import CHECKPOINT_TIMEOUT_SECONDS
from agent.logger import AgentLogger
from agent.session import Session
from ui.logic import (
    APPROVAL_PENDING_REPLY,
    format_status_line,
    format_stop_message,
    get_output_files,
    map_tool_error,
    parse_slash_command,
    render_untrusted,
)

_WELCOME = """\
Welcome! I'm your **CV-tailoring agent**.

**What I can do:**
- Read a job posting and tailor your CV and cover letter to it
- Match your skills against the job requirements
- Prepare and submit your application after your explicit approval

**Example requests:**
- `Tailor my CV for the job at mock://jobs/job_001`
- `Check how well I match the posting at mock://jobs/job_005`

> **I never submit anything without your explicit approval click.**

Type `/new` to reset the session, `/status` for current info, `/files` to list generated files.
"""


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

def _build_model():
    """Return (model, warning_str_or_None). Falls back to FakeModel if key missing."""
    model_name = os.environ.get("CV_AGENT_MODEL", "fake").lower()
    if model_name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return _fake_model(), "OpenAI key missing – running with the fake model."
        try:
            from agent.model import OpenAIModel
            return OpenAIModel(), None
        except Exception as exc:
            return _fake_model(), str(exc)
    return _fake_model(), None


def _fake_model():
    from agent.fake_model import FakeModel
    from agent.__main__ import FAKE_WALKTHROUGH_RESPONSES
    return FakeModel(FAKE_WALKTHROUGH_RESPONSES)


# ---------------------------------------------------------------------------
# Chat lifecycle
# ---------------------------------------------------------------------------

@cl.on_chat_start
async def on_chat_start():
    model, warning = _build_model()
    if warning:
        await cl.Message(content=f"⚠️ {warning}").send()

    loop = asyncio.get_running_loop()

    # Mutable holder so present_fn (defined here) can receive per-message context.
    ctx_holder: dict = {"ctx": None}
    cl.user_session.set("ctx_holder", ctx_holder)
    cl.user_session.set("approval_pending", False)
    cl.user_session.set("approval_msg", None)

    def present_fn(review_text: str) -> None:
        """
        Called from the worker thread when the agent requests approval.
        Posts the review message with Approve/Reject buttons, then returns
        (the ChatCheckpoint queue handles the subsequent wait).
        """
        ctx = ctx_holder.get("ctx")
        done: concurrent.futures.Future = concurrent.futures.Future()

        async def _post() -> None:
            try:
                await _show_approval_request(review_text)
                done.set_result(None)
            except Exception as exc:
                done.set_exception(exc)

        # Schedule _post on the event loop, restoring the Chainlit context.
        if ctx is not None:
            loop.call_soon_threadsafe(
                lambda: loop.create_task(_post(), context=ctx)
            )
        else:
            asyncio.run_coroutine_threadsafe(_post(), loop)

        done.result(timeout=30)  # Block the worker until the message is posted.

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

    await cl.Message(content=_WELCOME).send()


@cl.on_chat_end
async def on_chat_end():
    """Reject any pending approval when the chat closes to unblock the worker thread."""
    checkpoint: ChatCheckpoint | None = cl.user_session.get("checkpoint")
    if checkpoint and cl.user_session.get("approval_pending", False):
        cl.user_session.set("approval_pending", False)
        checkpoint.submit_decision(False)


# ---------------------------------------------------------------------------
# Approval actions (the ONLY path that can approve a submission)
# ---------------------------------------------------------------------------

@cl.action_callback("approve_submission")
async def on_approve(action: cl.Action):
    if not cl.user_session.get("approval_pending", False):
        return  # Idempotent — ignore second click after timeout/reject
    cl.user_session.set("approval_pending", False)
    await action.remove()
    await cl.Message(content="✅ **Approved.** Submitting…").send()
    checkpoint: ChatCheckpoint = cl.user_session.get("checkpoint")
    checkpoint.submit_decision(True)


@cl.action_callback("reject_submission")
async def on_reject(action: cl.Action):
    if not cl.user_session.get("approval_pending", False):
        return
    cl.user_session.set("approval_pending", False)
    await action.remove()
    await cl.Message(content="❌ **Rejected.** Submission cancelled.").send()
    checkpoint: ChatCheckpoint = cl.user_session.get("checkpoint")
    checkpoint.submit_decision(False)


async def _show_approval_request(review_text: str) -> None:
    """Post the review text with Approve / Reject buttons."""
    cl.user_session.set("approval_pending", True)
    safe = render_untrusted(review_text, max_chars=2000)
    actions = [
        cl.Action(name="approve_submission", payload={"value": "approve"}, label="✅ Approve"),
        cl.Action(name="reject_submission",  payload={"value": "reject"},  label="❌ Reject"),
    ]
    msg = await cl.Message(
        content=(
            "**Application Review**\n\n"
            + safe
            + "\n\n*Use the buttons below to approve or reject this submission.*"
        ),
        actions=actions,
    ).send()
    cl.user_session.set("approval_msg", msg)


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------

@cl.on_message
async def on_message(message: cl.Message):
    text = message.content.strip()

    # --- slash commands ---
    command, args = parse_slash_command(text)
    if command:
        await _handle_slash(command, args)
        return

    # --- approval guard: text input never approves ---
    if cl.user_session.get("approval_pending", False):
        await cl.Message(content=APPROVAL_PENDING_REPLY).send()
        return

    session: Session = cl.user_session.get("session")
    loop: asyncio.AbstractEventLoop = cl.user_session.get("loop")
    ctx_holder: dict = cl.user_session.get("ctx_holder")

    # Capture Chainlit context so present_fn can restore it in the worker thread.
    ctx = contextvars.copy_context()
    ctx_holder["ctx"] = ctx

    # Asyncio queue for step events pushed from the worker thread.
    step_queue: asyncio.Queue = asyncio.Queue()

    def on_step_fn(event: dict) -> None:
        # put_nowait is sync; call_soon_threadsafe is the safe cross-thread call.
        loop.call_soon_threadsafe(step_queue.put_nowait, event)

    session._on_step = on_step_fn

    # Run session.send in the thread pool so the event loop is never blocked.
    send_task = asyncio.create_task(
        loop.run_in_executor(None, session.send, text)
    )

    # Drain step events while the agent runs.
    while not send_task.done():
        try:
            event = await asyncio.wait_for(step_queue.get(), timeout=0.1)
            await _display_step(event)
        except asyncio.TimeoutError:
            pass

    # Drain any remaining events that arrived just before send_task finished.
    while not step_queue.empty():
        try:
            event = step_queue.get_nowait()
            await _display_step(event)
        except asyncio.QueueEmpty:
            break

    # Retrieve result (re-raises if the executor raised).
    try:
        result = send_task.result()
    except Exception as exc:
        await cl.Message(content=f"Unexpected error: {type(exc).__name__}: {exc}").send()
        return

    await _handle_result(result, session)


# ---------------------------------------------------------------------------
# Step display
# ---------------------------------------------------------------------------

async def _display_step(event: dict) -> None:
    """Show one tool call as a Chainlit step."""
    tool = event.get("tool", "(unknown)")
    args_summary = str(event.get("arguments", {}))[:200]
    result = event.get("result", {})

    # Map tool errors to a human string; show raw result otherwise.
    if isinstance(result, dict) and "error" in result:
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


# ---------------------------------------------------------------------------
# Result handler
# ---------------------------------------------------------------------------

async def _handle_result(result: dict, session: Session) -> None:
    # Ensure approval_pending is cleared in all code paths.
    cl.user_session.set("approval_pending", False)

    stop_reason = result.get("stop_reason", "")
    answer = result.get("answer") or ""

    special = format_stop_message(stop_reason, answer)
    if special:
        await cl.Message(content=special).send()
        return

    if answer:
        await cl.Message(content=answer).send()

    status = format_status_line(
        total_steps=session._total_steps,
        total_cost_usd=0.0,  # Prices are 0.0 by default; show n/a
        stop_reason=stop_reason if stop_reason not in ("done", "") else None,
    )
    await cl.Message(content=f"_{status}_").send()


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------

async def _handle_slash(command: str, args: str) -> None:
    session: Session = cl.user_session.get("session")

    if command == "new":
        session.reset()
        await cl.Message(content="✨ Session reset. Start a new task!").send()

    elif command == "status":
        job_id = None
        ws = session._workflow_state
        if ws and isinstance(ws.get("job"), dict):
            job_id = ws["job"].get("job_id")
        status = format_status_line(total_steps=session._total_steps, total_cost_usd=0.0)
        await cl.Message(
            content=f"{status}\nCurrent job: **{job_id or 'none'}**"
        ).send()

    elif command == "files":
        files = get_output_files()
        if files:
            names = "\n".join(f"- `{f}`" for f in files)
            await cl.Message(content=f"Generated files:\n{names}").send()
        else:
            await cl.Message(content="No generated files found yet.").send()

    else:
        await cl.Message(
            content=f"Unknown command: `/{command}`.\nTry `/new`, `/status`, or `/files`."
        ).send()
