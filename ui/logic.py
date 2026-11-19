"""
Pure logic helpers for the CV-tailoring agent UI.

No Chainlit imports here — this module must be testable offline.
"""

import re
from pathlib import Path

from agent.config import SANDBOX_DIR
from agent.errors import ERROR_CODES


# ---------------------------------------------------------------------------
# Approval guard
# ---------------------------------------------------------------------------

APPROVAL_PENDING_REPLY = (
    "An approval decision is pending. "
    "Please use the **Approve** or **Reject** button above to continue."
)


# ---------------------------------------------------------------------------
# Untrusted-content renderer
# ---------------------------------------------------------------------------

def render_untrusted(text: str, max_chars: int = 600) -> str:
    """
    Safely render untrusted content (job titles, descriptions, tool outputs)
    inside a fenced code block so it cannot be interpreted as markdown or HTML.

    - Truncates at max_chars.
    - Strips C0/C1 control characters (keeps newline and tab).
    - Escapes & < > as HTML entities (defense in depth for renderers that
      partially parse fenced blocks).
    - Escapes triple-backtick sequences so they cannot break the fence.
    """
    if not text:
        return "```\n(empty)\n```"

    # Truncate
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n… (truncated at {max_chars} chars)"

    # Strip control chars except \n and \t
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Escape HTML special chars (& first to avoid double-escaping)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # Break up triple-backtick sequences so they cannot close the fence.
    # Replace ``` with ` ` ` (spaces between) to preserve readability.
    text = re.sub(r"`{3,}", lambda m: " ".join("`" * len(m.group())), text)

    return f"```\n{text}\n```"


# ---------------------------------------------------------------------------
# Tool error messages
# ---------------------------------------------------------------------------

_TOOL_ERROR_MAP: dict[str, str] = {
    "INVALID_ARGUMENTS":    "The agent provided invalid arguments to a tool.",
    "UNKNOWN_TOOL":         "The agent tried to call a tool that does not exist.",
    "NOT_FOUND":            "The requested resource (URL or file) was not found.",
    "EMPTY_POSTING":        "The job posting returned no usable content.",
    "PORTAL_DOWN":          "The job portal is currently unreachable.",
    "TIMEOUT":              "An operation exceeded its time limit.",
    "BAD_RESPONSE":         "The model returned a response that could not be parsed.",
    "DUPLICATE_SUBMISSION": "An application for this job has already been submitted.",
    "PATH_NOT_ALLOWED":     "The file path is outside the allowed sandbox directory.",
    "SITE_NOT_ALLOWED":     "The site is not in the allowed list; only approved job sites can be searched.",
    "SITE_BLOCKED":         "The job site blocked the request (captcha, login wall, or rate limit).",
}

_GENERIC_TOOL_ERROR = "An error occurred while running a tool."


def map_tool_error(error_code: str, message: str, retryable: bool) -> str:
    """Return a human-readable string for a tool error dict."""
    base = _TOOL_ERROR_MAP.get(error_code, _GENERIC_TOOL_ERROR)
    hint = (
        " The agent may retry automatically."
        if retryable
        else " You may need to rephrase your request or start a new session."
    )
    detail = f"\n\n_Tool message:_ {message}" if message else ""
    return f"{base}{hint}{detail}"


# ---------------------------------------------------------------------------
# Stop-reason messages
# ---------------------------------------------------------------------------

def format_stop_message(stop_reason: str, answer: str) -> str:
    """
    Return a user-friendly chat message for non-"done" stop reasons.
    Returns "" for "done" (caller handles the normal answer path).
    """
    if stop_reason == "model_unavailable":
        short = (answer or "unknown error")[:200]
        return (
            f"The model is not available right now ({short}). "
            "Nothing was submitted. "
            "Check credits or the API key and try again."
        )
    if stop_reason == "session_limit":
        return (
            "The session step limit has been reached. "
            "No further actions can be taken in this session. "
            "Please start a new chat to continue."
        )
    if stop_reason == "no_match":
        return (
            "The job requirements do not match your CV closely enough to proceed. "
            "Nothing was submitted."
        )
    if stop_reason == "repeated_call":
        return "The agent got stuck in a loop and was stopped automatically."
    if stop_reason == "max_steps":
        return "The agent reached the maximum number of steps for this run without finishing."
    if stop_reason == "user_rejected":
        return "The submission was rejected. Nothing was submitted."
    if stop_reason == "checkpoint_timeout":
        return "⏱ Approval timed out — nothing was submitted."
    # "done" and unrecognised reasons → no special message
    return ""


# ---------------------------------------------------------------------------
# Status line
# ---------------------------------------------------------------------------

def format_status_line(
    total_steps: int,
    total_cost_usd: float,
    stop_reason: str | None = None,
) -> str:
    """Format a compact one-line session summary."""
    parts = [f"Steps this session: **{total_steps}**"]

    if total_cost_usd and total_cost_usd > 0:
        parts.append(f"Cost: **${total_cost_usd:.4f}**")
    else:
        parts.append("Cost: n/a (prices not configured)")

    if stop_reason:
        parts.append(f"Stop reason: `{stop_reason}`")

    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Slash-command parser
# ---------------------------------------------------------------------------

def parse_slash_command(text: str) -> tuple[str | None, str]:
    """
    Parse a potential slash command.

    Returns (command_name, remainder_args) for "/cmd args",
    or (None, original_text) if the text is not a slash command.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None, text
    parts = stripped[1:].split(None, 1)
    command = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""
    return command, args


# ---------------------------------------------------------------------------
# Output-file listing
# ---------------------------------------------------------------------------

def get_output_files() -> list[str]:
    """List generated CV and cover-letter files in the sandbox output directory."""
    output_dir = Path(SANDBOX_DIR) / "output"
    if not output_dir.exists():
        return []
    files: list[str] = []
    for pattern in ("cv_*.md", "cover_letter_*.md"):
        files.extend(sorted(p.name for p in output_dir.glob(pattern)))
    return files
