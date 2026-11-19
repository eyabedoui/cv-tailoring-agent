"""
Sandbox management commands.

    python -m sandbox setup                      – create sandbox directory structure
    python -m sandbox seed                       – populate sandbox/postings/ with 25 postings
    python -m sandbox reset                      – delete state and output files (keep postings)
    python -m sandbox run                        – run the agent against job_001 with fake model
    python -m sandbox serve [--port N]           – start the Flask apply site
    python -m sandbox export-static [--dest D]   – export postings as static HTML site
    python -m sandbox export [--dest D]          – alias for export-static (JSON files kept for compat)

Calling seed() implies setup().
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

_BASE = Path(__file__).parent


def setup() -> None:
    """Create sandbox directory structure if it does not already exist."""
    for sub in ("postings", "output", "state"):
        (_BASE / sub).mkdir(parents=True, exist_ok=True)
    print(f"Sandbox directories created under {_BASE}")


def seed() -> None:
    """Seed sandbox/postings/ with 25 deterministic fictional job postings."""
    setup()
    from sandbox.seed import seed as _seed
    _seed(postings_dir=_BASE / "postings")


def reset() -> None:
    """
    Clear sandbox/output/ and sandbox/state/ contents.

    Deletes the files inside those directories (not the directories themselves)
    so the sandbox is ready for a fresh agent run.  Keeps sandbox/postings/
    and the static markdown files.
    """
    for sub in ("output", "state"):
        target = _BASE / sub
        target.mkdir(parents=True, exist_ok=True)
        for item in target.iterdir():
            if item.is_file():
                item.unlink(missing_ok=True)
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
    print("Sandbox output and state cleared.")


def run(job_url: str | None = None) -> None:
    """Run the agent with the fake model and auto-approval."""
    if job_url is None:
        from agent.sites import own_job_url
        job_url = own_job_url("job_001")
    cmd = [
        sys.executable, "-m", "agent",
        "--model", "fake",
        "--auto-approve",
        "--job-url", job_url,
    ]
    subprocess.run(cmd, check=True)


def serve(port: int = 5000, sandbox_dir: str | None = None) -> None:
    """Start the Flask apply site on 127.0.0.1:<port>."""
    from sandbox.site_app import create_app
    app = create_app(sandbox_dir=sandbox_dir)
    print(f"Sandbox server listening on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)


def export_static(dest: str | None = None, postings_dir: str | None = None) -> None:
    """
    Export all postings as a static HTML site (index + one page per posting).

    dest        – output root directory (default: sandbox/site/)
    postings_dir – where to read .json postings from (default: sandbox/postings/)

    Reads every *.json file in postings_dir so injection postings (job_901+) are
    included if they have been placed there.

    URL shape (compatible with GitHub Pages when OWN_SITE_BASE_URL points there):
        index.html          – listing of all postings
        jobs/<job_id>.html  – individual posting page (same template as live /jobs/<id>)

    Uses the same Jinja2 templates as the live Flask server (sandbox/templates/).
    Autoescape is ON; no |safe is used.
    """
    from jinja2 import Environment, FileSystemLoader

    _templates_dir = Path(__file__).parent / "templates"
    _postings_dir = Path(postings_dir) if postings_dir else _BASE / "postings"
    dest_path = Path(dest) if dest else _BASE / "site"
    jobs_out = dest_path / "jobs"
    jobs_out.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(_templates_dir)), autoescape=True)

    postings = []
    for path in sorted(_postings_dir.glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            postings.append(json.load(fh))

    job_tmpl = env.get_template("job.html")
    for posting in postings:
        html = job_tmpl.render(posting=posting)
        (jobs_out / f"{posting['job_id']}.html").write_text(html, encoding="utf-8")

    index_tmpl = env.get_template("index.html")
    html = index_tmpl.render(postings=postings)
    (dest_path / "index.html").write_text(html, encoding="utf-8")

    print(f"Exported {len(postings)} postings to {dest_path}")


def export(dest: str | None = None) -> None:
    """Alias for export_static (kept for backwards compatibility)."""
    export_static(dest=dest)


def setup_web() -> None:
    """
    Install Playwright Chromium required by browser-use for WEB_MODE=live.

    Safe to run multiple times; Playwright is idempotent.
    """
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
    )
    if result.returncode != 0:
        print("Warning: playwright install chromium failed — live browser automation will not work.")
        print("Install Playwright manually: pip install playwright && python -m playwright install chromium")
    else:
        print("Chromium installed via Playwright.")


def snapshot(url: str, snapshots_dir: str | None = None) -> None:
    """
    Fetch *url* with Firecrawl and save the markdown to sandbox/snapshots/<job_id>.json.

    The job_id is derived from the URL using the same hash used by FakePostingClient
    in replay mode.  Requires FIRECRAWL_API_KEY to be set.
    """
    import hashlib
    from agent.tools.clients import FirecrawlPostingClient
    from agent.sites import url_belongs_to_site, site_names

    _snapshots_dir = Path(snapshots_dir) if snapshots_dir else _BASE / "snapshots"
    _snapshots_dir.mkdir(parents=True, exist_ok=True)

    h = hashlib.sha256(url.encode()).hexdigest()[:8]
    site = "ext"
    for s in site_names():
        if url_belongs_to_site(url, s):
            site = s
            break
    job_id = f"{site}-{h}"

    client = FirecrawlPostingClient()
    result = client.fetch(url)

    if "error" in result:
        print(f"Error fetching {url!r}: {result['error']} – {result.get('message', '')}")
        return

    snapshot_path = _snapshots_dir / f"{job_id}.json"
    data = {
        "url": url,
        "job_id": job_id,
        "markdown": result.get("markdown", ""),
    }
    with open(snapshot_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"Saved snapshot {job_id} → {snapshot_path}")
