"""
Flask apply site for the CV-tailoring agent sandbox.

Routes:
    GET  /health              → {"status": "ok"}  (JSON)
    GET  /jobs/<job_id>       → HTML job posting page  (404 if not found)
    GET  /jobs/<job_id>.json  → JSON job posting  (for agent / API callers)
    GET  /apply/<job_id>      → HTML read-only CV + cover letter + submit form
                                400 if job_id invalid format
                                404 if job not found
                                404 if output files not saved yet
                                200 "Already applied." if duplicate
    POST /apply/<job_id>      → record application; files derived from job_id
                                400 if job_id invalid or files missing
                                409 if already applied

Autoescape is ON (Flask default for .html templates).  No |safe used anywhere.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

from sandbox.portal import Portal


def _valid_job_id(job_id: str) -> bool:
    from agent.job_ids import is_valid_job_id
    return is_valid_job_id(job_id)


def create_app(sandbox_dir: str | None = None) -> Flask:
    """Application factory.  Pass sandbox_dir to override the default location."""
    app = Flask(__name__)
    portal = Portal(sandbox_dir=sandbox_dir)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    # ------------------------------------------------------------------
    # Job posting — HTML
    # ------------------------------------------------------------------

    @app.get("/jobs/<job_id>")
    def view_job(job_id: str):
        posting = portal.get_posting(job_id)
        if posting is None:
            abort(404)
        return render_template("job.html", posting=posting)

    # ------------------------------------------------------------------
    # Job posting — JSON (agent / API consumers)
    # ------------------------------------------------------------------

    @app.get("/jobs/<job_id>.json")
    def view_job_json(job_id: str):
        posting = portal.get_posting(job_id)
        if posting is None:
            return jsonify({"error": "NOT_FOUND", "message": f"Job {job_id!r} not found"}), 404
        return jsonify(posting)

    # ------------------------------------------------------------------
    # Apply — GET (read-only view + form)
    # ------------------------------------------------------------------

    @app.get("/apply/<job_id>")
    def apply_get(job_id: str):
        if not _valid_job_id(job_id):
            abort(400)

        posting = portal.get_posting(job_id)
        if posting is None:
            abort(404)

        cv_file = portal.output_dir / f"cv_{job_id}.md"
        cl_file = portal.output_dir / f"cover_letter_{job_id}.md"

        if portal.has_applied(job_id):
            return render_template("apply.html", posting=posting, already_applied=True,
                                   missing_files=False, cv_text="", cl_text="")

        if not cv_file.exists() or not cl_file.exists():
            return render_template("apply.html", posting=posting, already_applied=False,
                                   missing_files=True, cv_text="", cl_text=""), 404

        cv_text = cv_file.read_text(encoding="utf-8")
        cl_text = cl_file.read_text(encoding="utf-8")

        return render_template("apply.html", posting=posting, already_applied=False,
                               missing_files=False, cv_text=cv_text, cl_text=cl_text)

    # ------------------------------------------------------------------
    # Apply — POST (from form or agent; paths derived from job_id)
    # ------------------------------------------------------------------

    @app.post("/apply/<job_id>")
    def apply_post(job_id: str):
        if not _valid_job_id(job_id):
            return jsonify({"error": "INVALID_ARGUMENTS",
                            "message": f"Invalid job_id format: {job_id!r}"}), 400

        posting = portal.get_posting(job_id)
        if posting is None:
            return jsonify({"error": "NOT_FOUND",
                            "message": f"Job {job_id!r} not found"}), 404

        cv_file = portal.output_dir / f"cv_{job_id}.md"
        cl_file = portal.output_dir / f"cover_letter_{job_id}.md"

        if not cv_file.exists() or not cl_file.exists():
            return jsonify({"error": "INVALID_ARGUMENTS",
                            "message": "Output files not found. Save CV and cover letter first."}), 400

        if portal.has_applied(job_id):
            return jsonify({"error": "DUPLICATE_SUBMISSION",
                            "message": f"An application for {job_id!r} has already been submitted"}), 409

        # Paths stored relative to sandbox_dir root
        cv_rel = str(Path("output") / f"cv_{job_id}.md")
        cl_rel = str(Path("output") / f"cover_letter_{job_id}.md")
        portal.record_application(job_id, cv_rel, cl_rel)

        return jsonify({"status": "submitted", "application_id": f"app_{job_id}"})

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "NOT_FOUND", "message": str(e)}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "INVALID_ARGUMENTS", "message": str(e)}), 400

    return app
