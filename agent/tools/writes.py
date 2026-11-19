"""
Real implementations of the two write tools: save_tailored_cv, submit_application.

Both functions accept an optional _portal parameter for test injection.
When called through execute_tool the parameter is absent and the
module-level default portal (sandbox/) is used.
"""

import os
from pathlib import Path

from agent.config import SANDBOX_DIR
from agent.errors import (
    make_error,
    PATH_NOT_ALLOWED,
    DUPLICATE_SUBMISSION,
    INVALID_ARGUMENTS,
    BAD_RESPONSE,
)
from sandbox.faults import check_fault
from sandbox.portal import Portal

# Lazy-initialised default portal; tests may replace this via monkeypatching.
_portal: Portal | None = None


def _get_portal() -> Portal:
    global _portal
    if _portal is None:
        _portal = Portal()
    return _portal


def save_tailored_cv(
    text: str,
    job_id: str,
    kind: str,
    _portal: Portal | None = None,
) -> dict:
    """Write text to sandbox/output/{kind}_{job_id}.md using an atomic rename."""
    portal = _portal if _portal is not None else _get_portal()
    portal.output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{kind}_{job_id}.md"
    output_path = portal.output_dir / filename

    # Belt-and-suspenders: confirm the resolved path stays inside output_dir.
    try:
        output_path.resolve().relative_to(portal.output_dir.resolve())
    except ValueError:
        return make_error(
            PATH_NOT_ALLOWED,
            f"Computed path {output_path!r} is outside the allowed output directory",
        )

    tmp = output_path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, output_path)
    except OSError as exc:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        return make_error(PATH_NOT_ALLOWED, f"Could not write file: {exc}")

    return {"path": str(output_path), "saved": True}


def submit_application(
    cv_path: str,
    cover_letter_path: str,
    job_id: str,
    _portal: Portal | None = None,
    _submit_client=None,
) -> dict:
    """Record a submitted application.  Rejects path traversal and duplicates."""
    portal = _portal if _portal is not None else _get_portal()

    fault = check_fault("submit", portal.state_dir)
    if fault is not None:
        return fault

    # Validate job_id format
    from agent.job_ids import is_valid_job_id
    if not is_valid_job_id(job_id):
        return make_error(
            INVALID_ARGUMENTS,
            f"job_id must match job_NNN or site-xxxxxxxx, got {job_id!r}",
        )

    # PATH_NOT_ALLOWED: reject absolute paths and ".." traversal.
    # Path.is_absolute() misses Unix-style "/..." on Windows, so also check
    # for a leading "/" explicitly.
    for label, path_str in (
        ("cv_path", cv_path),
        ("cover_letter_path", cover_letter_path),
    ):
        p = Path(path_str)
        if p.is_absolute() or path_str.startswith("/") or ".." in p.parts:
            return make_error(
                PATH_NOT_ALLOWED,
                f"{label} must be a relative path without '..' components, got {path_str!r}",
            )

    # File existence check: both files must exist inside output_dir.
    for label, path_str in (
        ("cv_path", cv_path),
        ("cover_letter_path", cover_letter_path),
    ):
        full_path = portal.output_dir / path_str
        if not full_path.exists():
            return make_error(
                INVALID_ARGUMENTS,
                f"{label} not found: {path_str!r} does not exist in the output directory",
            )

    # WEB_MODE=live or explicit submit client: submit via browser
    mode = os.environ.get("WEB_MODE", "fake").lower().strip()
    if mode == "live" or _submit_client is not None:
        from agent.tools.clients import BrowserSubmitClient
        from agent.sites import own_apply_url
        if mode == "live" and _submit_client is None:
            from agent.tools.throttle import throttle
            throttle("127.0.0.1")
        client = _submit_client if _submit_client is not None else BrowserSubmitClient()
        result = client.submit(job_id, own_apply_url(job_id))
        if mode == "live" and _submit_client is None:
            from agent.tools.usage_log import log_usage
            log_usage("submit_application", "127.0.0.1", result.get("status", result.get("error", "unknown")))

        # Reconcile browser result with portal state.
        # The browser navigates to the Flask apply server, which writes to the portal.
        # If the portal record and browser result disagree, return the portal truth.
        applied = portal.has_applied(job_id)
        if "error" not in result:
            # Browser claims success — verify the portal has the record.
            if not applied:
                return make_error(
                    BAD_RESPONSE,
                    f"Submit agent reported success for {job_id!r} but no portal record was found",
                )
        else:
            # Browser reported failure — check if portal actually recorded it.
            if applied:
                return {"status": "submitted", "application_id": f"app_{job_id}"}

        return result

    # WEB_MODE=fake: record directly via portal.
    if portal.has_applied(job_id):
        return make_error(
            DUPLICATE_SUBMISSION,
            f"An application for {job_id!r} has already been submitted",
        )

    portal.record_application(job_id, cv_path, cover_letter_path)

    return {
        "status": "submitted",
        "application_id": f"app_{job_id}",
    }
