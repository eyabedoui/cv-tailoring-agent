
"""
Tool registry for the CV-tailoring agent.

The registry exposes the available tools to the model
and executes the selected tool.
"""

from pydantic import ValidationError

from agent.tools import reads
from agent.tools import writes
from agent.tools import search as search_mod
from agent.errors import make_error, INVALID_ARGUMENTS, UNKNOWN_TOOL, BAD_RESPONSE, SITE_NOT_ALLOWED
from agent.tools.schemas import TOOL_SCHEMA_MAP


TOOL_FUNCTIONS = {
    "read_job_posting": reads.read_job_posting,
    "read_master_cv": reads.read_master_cv,
    "match_skills": reads.match_skills,
    "check_format": reads.check_format,
    "save_tailored_cv": writes.save_tailored_cv,
    "submit_application": writes.submit_application,
    "find_jobs": search_mod.find_jobs,
}


def _make_validation_message(exc: ValidationError) -> str:
    """Return a short, readable summary of pydantic validation errors."""
    parts = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err["loc"]) if err["loc"] else "input"
        parts.append(f"{field}: {err['msg']}")
    return "; ".join(parts)


TOOL_SCHEMAS = [
    {
        "name": "find_jobs",
        "description": "Search for job postings on an allowed site.",
        "parameters": {
            "query": "string",
            "site": "string",
        },
        "input_schema": TOOL_SCHEMA_MAP["find_jobs"][0].model_json_schema(),
    },
    {
        "name": "read_job_posting",
        "description": "Read a job posting using its URL.",
        "parameters": {
            "url": "string",
        },
        "input_schema": TOOL_SCHEMA_MAP["read_job_posting"][0].model_json_schema(),
    },
    {
        "name": "read_master_cv",
        "description": "Read the user's master CV.",
        "parameters": {},
        "input_schema": TOOL_SCHEMA_MAP["read_master_cv"][0].model_json_schema(),
    },
    {
        "name": "match_skills",
        "description": "Compare CV skills with job requirements.",
        "parameters": {
            "cv_text": "string",
            "job": "object",
        },
        "input_schema": TOOL_SCHEMA_MAP["match_skills"][0].model_json_schema(),
    },
    {
        "name": "check_format",
        "description": "Check the formatting of a CV.",
        "parameters": {
            "cv_text": "string",
        },
        "input_schema": TOOL_SCHEMA_MAP["check_format"][0].model_json_schema(),
    },
    {
        "name": "save_tailored_cv",
        "description": "Save a tailored CV or cover letter.",
        "parameters": {
            "text": "string",
            "job_id": "string",
            "kind": "string",
        },
        "input_schema": TOOL_SCHEMA_MAP["save_tailored_cv"][0].model_json_schema(),
    },
    {
        "name": "submit_application",
        "description": "Submit an application after human approval.",
        "parameters": {
            "cv_path": "string",
            "cover_letter_path": "string",
            "job_id": "string",
        },
        "input_schema": TOOL_SCHEMA_MAP["submit_application"][0].model_json_schema(),
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

    # Pre-schema check: http/https URLs to read_job_posting must pass the
    # site allowlist or be from our own site; other URLs return SITE_NOT_ALLOWED
    # rather than INVALID_ARGUMENTS so the model knows why the URL was rejected.
    if tool_name == "read_job_posting":
        url = arguments.get("url", "")
        if isinstance(url, str) and url.lower().startswith(("http://", "https://")):
            from agent.sites import is_url_allowed, is_own_url, site_names
            if not is_url_allowed(url) and not is_own_url(url):
                names = ", ".join(sorted(site_names()))
                return make_error(
                    SITE_NOT_ALLOWED,
                    f"URL is not from an allowed site. Allowed sites: {names}.",
                )

    in_model, out_model = TOOL_SCHEMA_MAP[tool_name]

    try:
        in_model(**arguments)
    except ValidationError as exc:
        return make_error(INVALID_ARGUMENTS, _make_validation_message(exc))
    except TypeError as exc:
        return make_error(INVALID_ARGUMENTS, str(exc))

    tool_function = TOOL_FUNCTIONS[tool_name]

    try:
        raw = tool_function(**arguments)
    except Exception as exc:
        return make_error(BAD_RESPONSE, str(exc))

    if isinstance(raw, dict) and "error" in raw:
        return raw

    try:
        return out_model(**raw).model_dump()
    except (ValidationError, TypeError) as exc:
        return make_error(BAD_RESPONSE, f"Tool returned invalid output: {exc}")
