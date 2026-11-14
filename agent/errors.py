
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
}


def make_error(code: str, message: str, retryable: bool = False) -> dict:
    """Return a structured error dict the model can read."""
    return {
        "error": code,
        "message": message,
        "retryable": retryable,
    }


def is_error(result) -> bool:
    """Return True if result is an error dict produced by make_error."""
    return (
        isinstance(result, dict)
        and "error" in result
        and result["error"] in ERROR_CODES
    )
