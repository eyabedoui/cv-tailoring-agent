"""
Per-session CV upload: validation, cleaning and storage.

An uploaded CV is untrusted input. It is limited to plain text (.md or .txt),
size-capped, stripped of HTML tags, control characters and zero-width characters,
and stored in a per-session folder so one chat never sees another chat's CV.
The agent reads it through the normal read_master_cv tool, whose result is
already wrapped as untrusted data by the loop.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from agent.config import SANDBOX_DIR

ALLOWED_SUFFIXES = (".md", ".txt")
MAX_UPLOAD_BYTES = 100_000
MAX_CV_CHARS = 20_000
MIN_CV_CHARS = 50

_ZERO_WIDTH = "​‌‍⁠﻿"
_TAG_RE = re.compile(r"<[^>]{0,500}>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_-]")


class CvUploadError(ValueError):
    """Raised with a message that is safe to show to the user."""


def clean_cv_text(raw: str) -> str:
    """Strip zero-width and control characters and HTML tags, then cap the length."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    for ch in _ZERO_WIDTH:
        text = text.replace(ch, "")
    text = _CONTROL_RE.sub("", text)
    text = _TAG_RE.sub("", text)
    return text.strip()[:MAX_CV_CHARS]


def validate_upload(filename: str, data: bytes) -> str:
    """Return the cleaned CV text, or raise CvUploadError."""
    name = (filename or "").lower()
    if not name.endswith(ALLOWED_SUFFIXES):
        raise CvUploadError("Only .md or .txt CV files are accepted (PDF and Word are not supported yet).")
    if len(data) > MAX_UPLOAD_BYTES:
        raise CvUploadError(f"The file is too large (limit {MAX_UPLOAD_BYTES // 1000} KB).")
    try:
        raw = data.decode("utf-8")
    except UnicodeDecodeError:
        raise CvUploadError("The file is not valid UTF-8 text.") from None
    text = clean_cv_text(raw)
    if len(text) < MIN_CV_CHARS:
        raise CvUploadError("The file is almost empty. Please attach your full CV as text.")
    return text


def session_cv_path(session_id: str) -> Path:
    safe = _SAFE_ID_RE.sub("", session_id or "")[:64]
    if not safe:
        raise CvUploadError("Invalid session.")
    return Path(SANDBOX_DIR) / "uploads" / safe / "master_cv.md"


def save_session_cv(session_id: str, filename: str, data: bytes) -> Path:
    text = validate_upload(filename, data)
    path = session_cv_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def delete_session_cv(session_id: str) -> None:
    try:
        shutil.rmtree(session_cv_path(session_id).parent, ignore_errors=True)
    except CvUploadError:
        pass
