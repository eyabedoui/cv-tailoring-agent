
"""
Tool registry for the CV-tailoring agent.

The registry exposes the available tools to the model
and executes the selected tool.
"""

from agent.tools import stubs
from agent.errors import make_error, INVALID_ARGUMENTS, UNKNOWN_TOOL, BAD_RESPONSE


TOOL_FUNCTIONS = {
    "read_job_posting": stubs.read_job_posting,
    "read_master_cv": stubs.read_master_cv,
    "match_skills": stubs.match_skills,
    "check_format": stubs.check_format,
    "save_tailored_cv": stubs.save_tailored_cv,
    "submit_application": stubs.submit_application,
}


TOOL_SCHEMAS = [
    {
        "name": "read_job_posting",
        "description": "Read a job posting using its URL.",
        "parameters": {
            "url": "string",
        },
    },
    {
        "name": "read_master_cv",
        "description": "Read the user's master CV.",
        "parameters": {},
    },
    {
        "name": "match_skills",
        "description": "Compare CV skills with job requirements.",
        "parameters": {
            "cv_text": "string",
            "job": "object",
        },
    },
    {
        "name": "check_format",
        "description": "Check the formatting of a CV.",
        "parameters": {
            "cv_text": "string",
        },
    },
    {
        "name": "save_tailored_cv",
        "description": "Save a tailored CV or cover letter.",
        "parameters": {
            "text": "string",
            "job_id": "string",
            "kind": "string",
        },
    },
    {
        "name": "submit_application",
        "description": "Submit an application after human approval.",
        "parameters": {
            "cv_path": "string",
            "cover_letter_path": "string",
            "job_id": "string",
        },
    },
]


def execute_tool(tool_name: str, arguments: dict) -> dict:
    """
    Execute a tool by name with the supplied arguments.

    Returns an error dict (never raises) so the loop can forward the error
    to the model without crashing.
    """

    if tool_name not in TOOL_FUNCTIONS:
        return make_error(UNKNOWN_TOOL, f"Unknown tool: {tool_name}")

    tool_function = TOOL_FUNCTIONS[tool_name]

    try:
        return tool_function(**arguments)
    except TypeError as exc:
        return make_error(INVALID_ARGUMENTS, str(exc))
    except Exception as exc:
        return make_error(BAD_RESPONSE, str(exc))
