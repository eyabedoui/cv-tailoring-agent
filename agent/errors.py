
"""
Error contract for the CV-tailoring agent.

All tool errors and loop failures are expressed as error dicts so the model
receives a plain-text message it can act on instead of a Python traceback.
"""

INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
UNKNOWN_TOOL = "UNKNOWN_TOOL"
NOT_FOUND = "NOT_FOUND"
EMPTY_POSTING = "EMPTY_POSTING"
PORTAL_DOWN = "PORTAL_DOWN"
TIMEOUT = "TIMEOUT"
BAD_RESPONSE = "BAD_RESPONSE"
DUPLICATE_SUBMISSION = "DUPLICATE_SUBMISSION"
PATH_NOT_ALLOWED = "PATH_NOT_ALLOWED"
SITE_NOT_ALLOWED = "SITE_NOT_ALLOWED"
SITE_BLOCKED = "SITE_BLOCKED"

ERROR_CODES = {
    INVALID_ARGUMENTS,
    UNKNOWN_TOOL,
    NOT_FOUND,
    EMPTY_POSTING,
    PORTAL_DOWN,
    TIMEOUT,
    BAD_RESPONSE,
    DUPLICATE_SUBMISSION,
    PATH_NOT_ALLOWED,
    SITE_NOT_ALLOWED,
    SITE_BLOCKED,
}


def make_error(code: str, message: str, retryable: bool = False) -> dict:
    """Return a structured error dict the model can read."""
    return {
        "error": code,
        "message": message,
        "retryable": retryable,
    }


def is_error(result) -> bool:
    """Return True if result is an error dict (has a string 'error' key).

    Any dict with a string-valued 'error' key is treated as an error so that
    unknown fault codes (e.g. 'FAULT_INJECTED') don't slip through as valid
    state updates.  ERROR_CODES remains the list of *known* codes.
    """
    return (
        isinstance(result, dict)
        and "error" in result
        and isinstance(result["error"], str)
    )
