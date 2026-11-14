"""
Sandbox portal: read job postings and track submitted applications.

All data is fictional.  No network access.  File I/O only.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from agent.config import SANDBOX_DIR


class Portal:
    """Thin file-system interface for the fictional job-posting sandbox."""

    def __init__(self, sandbox_dir: str | None = None) -> None:
        base = Path(sandbox_dir) if sandbox_dir else Path(SANDBOX_DIR)
        self.postings_dir = base / "postings"
        self.state_dir = base / "state"
        self.output_dir = base / "output"
        self.applications_file = self.state_dir / "applications.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_posting(self, job_id: str) -> dict | None:
        """Return the parsed posting dict, or None if not found."""
        path = self.postings_dir / f"{job_id}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def has_applied(self, job_id: str) -> bool:
        """Return True if an application for job_id was already recorded."""
        if not self.applications_file.exists():
            return False
        with open(self.applications_file, encoding="utf-8") as fh:
            apps = json.load(fh)
        return job_id in apps

    # ------------------------------------------------------------------
    # Write operations (atomic)
    # ------------------------------------------------------------------

    def record_application(
        self,
        job_id: str,
        cv_path: str,
        cover_letter_path: str,
    ) -> None:
        """Atomically record a submitted application."""
        if self.applications_file.exists():
            with open(self.applications_file, encoding="utf-8") as fh:
                apps = json.load(fh)
        else:
            apps = {}

        apps[job_id] = {
            "cv_path": cv_path,
            "cover_letter_path": cover_letter_path,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }

        tmp = self.applications_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(apps, fh, indent=2)
        os.replace(tmp, self.applications_file)
