"""
Real implementations of the two write tools: save_tailored_cv, submit_application.

Both functions accept an optional _portal parameter for test injection.
When called through execute_tool the parameter is absent and the
module-level default portal (sandbox/) is used.
"""

import os
from pathlib import Path

from agent.config import SANDBOX_DIR
from agent.errors import make_error, PATH_NOT_ALLOWED, DUPLICATE_SUBMISSION
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
) -> dict:
    """Record a submitted application.  Rejects path traversal and duplicates."""
    portal = _portal if _portal is not None else _get_portal()

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

    # DUPLICATE_SUBMISSION: each job may only be submitted once.
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
