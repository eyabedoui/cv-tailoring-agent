"""
FAULT_MODE injection for sandbox portal operations.

Set the FAULT_MODE environment variable before running the agent to trigger
one of the following behaviours:

  down             – portal permanently unavailable (PORTAL_DOWN, retryable)
  timeout          – portal timed out (TIMEOUT, retryable)
  bad_response     – portal returned a malformed response (BAD_RESPONSE)
  fail_once        – first call fails (PORTAL_DOWN, retryable), all later
                     calls succeed; state tracked in state/fault_state.json
  reject_duplicate – submit_application always returns DUPLICATE_SUBMISSION
  blocked          – find_jobs returns SITE_BLOCKED (search context only)
  unknown          – returns an error code not in the known ERROR_CODES set,
                     testing agent resilience to unexpected responses

FAULT_MODE is read on every call so it can be changed between tests via
monkeypatch.setenv / os.environ without restarting the process.
"""

import json
import os
from pathlib import Path

from agent.errors import BAD_RESPONSE, DUPLICATE_SUBMISSION, PORTAL_DOWN, SITE_BLOCKED, TIMEOUT, make_error

_FAULT_STATE_FILENAME = "fault_state.json"


def check_fault(context: str, state_dir: Path) -> dict | None:
    """
    Inspect FAULT_MODE and return an error dict when a fault should fire,
    or None when the caller should proceed normally.

    context: "read" (read_job_posting) or "submit" (submit_application).
    state_dir: portal's state directory — used only by the fail_once mode.
    """
    mode = os.environ.get("FAULT_MODE", "").strip().lower()
    if not mode:
        return None

    if mode == "down":
        return make_error(PORTAL_DOWN, "Sandbox portal is unavailable (FAULT_MODE=down)", retryable=True)

    if mode == "timeout":
        return make_error(TIMEOUT, "Sandbox portal request timed out (FAULT_MODE=timeout)", retryable=True)

    if mode == "bad_response":
        return make_error(BAD_RESPONSE, "Sandbox portal returned malformed data (FAULT_MODE=bad_response)")

    if mode == "fail_once":
        return _fail_once(state_dir)

    if mode == "reject_duplicate" and context == "submit":
        return make_error(
            DUPLICATE_SUBMISSION,
            "Portal rejected duplicate application (FAULT_MODE=reject_duplicate)",
        )

    if mode == "blocked" and context in ("search", "read"):
        return make_error(
            SITE_BLOCKED,
            "Site blocked automation (FAULT_MODE=blocked)",
            retryable=False,
        )

    if mode == "unknown":
        # Return an unrecognised error code so is_error() returns False,
        # testing whether the agent handles unexpected response shapes.
        return {
            "error": "FAULT_INJECTED",
            "message": "Unknown error from portal (FAULT_MODE=unknown)",
            "retryable": False,
        }

    return None


def _fail_once(state_dir: Path) -> dict | None:
    """Fire on the first call; succeed on all subsequent calls."""
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / _FAULT_STATE_FILENAME

    if state_file.exists():
        with open(state_file, encoding="utf-8") as fh:
            state = json.load(fh)
        if state.get("fail_once_fired", False):
            return None  # already fired; proceed normally

    # Record the fault as fired (atomic write), then return the error.
    new_state = {"fail_once_fired": True}
    tmp = state_file.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(new_state, fh)
    os.replace(tmp, state_file)

    return make_error(
        PORTAL_DOWN,
        "First call failed as requested (FAULT_MODE=fail_once)",
        retryable=True,
    )
