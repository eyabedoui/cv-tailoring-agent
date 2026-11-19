"""
Sandbox management commands.

    python -m sandbox setup                      – create sandbox dirs + install Playwright Chromium
    python -m sandbox setup-web                  – alias for setup (Chromium install step only)
    python -m sandbox seed                       – populate sandbox/postings/ with 25 postings
    python -m sandbox reset                      – delete state and output files (keep postings)
    python -m sandbox run                        – run the agent against job_001 with fake model
    python -m sandbox serve [--port N]           – start the Flask apply site
    python -m sandbox export-static [--dest D]   – export postings as static HTML site
    python -m sandbox export [--dest D]          – alias for export-static (JSON files kept for compat)
    python -m sandbox snapshot <url>             – fetch URL with Firecrawl, save snapshot
    python -m sandbox smoke-web                  – MANUAL: integration smoke test (requires live keys)

Calling seed() implies setup().
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

_BASE = Path(__file__).parent


def setup() -> None:
    """Create sandbox directory structure and install Playwright Chromium (idempotent)."""
    for sub in ("postings", "output", "state", "snapshots"):
        (_BASE / sub).mkdir(parents=True, exist_ok=True)
    print(f"Sandbox directories created under {_BASE}")
    setup_web()


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


_SCRUB_EMAIL_RE = None
_SCRUB_PHONE_RE = None

_EXCERPT_MAX_CHARS = 3000


def _scrub_pii(text: str) -> str:
    """Replace email addresses and phone numbers with placeholder tokens."""
    import re
    global _SCRUB_EMAIL_RE, _SCRUB_PHONE_RE
    if _SCRUB_EMAIL_RE is None:
        _SCRUB_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
        _SCRUB_PHONE_RE = re.compile(r"\+?[\d][\d\s\-\(\)\.]{6,}[\d]")
    text = _SCRUB_EMAIL_RE.sub("[EMAIL]", text)
    text = _SCRUB_PHONE_RE.sub("[PHONE]", text)
    return text


def snapshot(url: str, snapshots_dir: str | None = None, full: bool = False) -> None:
    """
    Fetch *url* with Firecrawl and save the markdown to sandbox/snapshots/<job_id>.json.

    The job_id is derived from the URL using the same hash used by FakePostingClient
    in replay mode.  Requires FIRECRAWL_API_KEY to be set.

    By default only the first 3000 characters of the scraped markdown are saved
    (after PII scrubbing).  Pass full=True / --full to store the complete text.

    PII scrubbing: email addresses and phone numbers are replaced with tokens
    before saving.
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

    markdown = result.get("markdown", "")
    markdown = _scrub_pii(markdown)
    if not full:
        markdown = markdown[:_EXCERPT_MAX_CHARS]

    snapshot_path = _snapshots_dir / f"{job_id}.json"
    data = {
        "url": url,
        "job_id": job_id,
        "markdown": markdown,
    }
    with open(snapshot_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"Saved snapshot {job_id} → {snapshot_path}")


def smoke_web() -> None:
    """
    MANUAL integration smoke test for WEB_MODE=live.

    Never call this from pytest — it requires real API keys and a running
    Flask apply site.  Aborts immediately with a clear error if either
    OPENAI_API_KEY or FIRECRAWL_API_KEY is missing.

    Checks performed:
      1. Flask /health endpoint responds {"status":"ok"}
      2. find_jobs on each allowed site returns at least one result
      3. read_job_posting on the first result of each site succeeds
      4. submit_application for one job_id succeeds (or is a duplicate)
      5. Prints a pass/fail table and usage-log totals at the end
    """
    import os
    import json as _json
    import urllib.request
    from agent.sites import site_names, own_base_url
    from agent.tools.search import find_jobs
    from agent.tools.reads import read_job_posting
    from agent.tools.writes import submit_application

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not openai_key or not firecrawl_key:
        missing = []
        if not openai_key:
            missing.append("OPENAI_API_KEY")
        if not firecrawl_key:
            missing.append("FIRECRAWL_API_KEY")
        print(f"ABORT: Missing environment variable(s): {', '.join(missing)}")
        print("Export those variables before running smoke-web.")
        sys.exit(1)

    rows: list[tuple[str, str, str]] = []  # (check, detail, status)

    def _pass(check: str, detail: str = "") -> None:
        rows.append((check, detail, "PASS"))

    def _fail(check: str, detail: str = "") -> None:
        rows.append((check, detail, "FAIL"))

    # 1. Health check
    base_url = own_base_url()
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=5) as resp:
            body = _json.loads(resp.read())
        if body.get("status") == "ok":
            _pass("health", base_url)
        else:
            _fail("health", f"unexpected body: {body}")
    except Exception as exc:
        _fail("health", str(exc))

    # 2–3. Per-site search + read
    first_job_url: str | None = None
    for site in site_names():
        search_result = find_jobs("software developer", site)
        if "error" in search_result or not search_result.get("jobs"):
            _fail(f"find_jobs/{site}", search_result.get("message", "no jobs returned"))
            continue
        _pass(f"find_jobs/{site}", f"{search_result['count']} results")

        job_url = search_result["jobs"][0]["url"]
        read_result = read_job_posting(job_url)
        if "error" in read_result:
            _fail(f"read/{site}", read_result.get("message", ""))
        else:
            _pass(f"read/{site}", read_result.get("job_id", ""))
            if first_job_url is None:
                first_job_url = job_url

    # 4. Submit (one attempt)
    if first_job_url is not None:
        from agent.tools.writes import save_tailored_cv
        from sandbox.portal import Portal
        portal = Portal()
        job_id = read_job_posting(first_job_url).get("job_id", "unknown")
        save_tailored_cv("CV placeholder", job_id, "cv", _portal=portal)
        save_tailored_cv("CL placeholder", job_id, "cover_letter", _portal=portal)
        sub_result = submit_application(
            f"cv_{job_id}.md", f"cover_letter_{job_id}.md", job_id, _portal=portal
        )
        if sub_result.get("status") == "submitted" or sub_result.get("error") == "DUPLICATE_SUBMISSION":
            _pass("submit", job_id)
        else:
            _fail("submit", sub_result.get("message", str(sub_result)))

    # 5. Print table
    col_w = max((len(r[0]) for r in rows), default=10) + 2
    print(f"\n{'Check':<{col_w}} {'Detail':<50} Status")
    print("-" * (col_w + 58))
    for check, detail, status in rows:
        print(f"{check:<{col_w}} {detail[:50]:<50} {status}")

    # Usage log totals
    log_path = _BASE / "usage_log.jsonl"
    if log_path.exists():
        entries = [_json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        by_tool: dict[str, int] = {}
        for e in entries:
            by_tool[e.get("tool", "?")] = by_tool.get(e.get("tool", "?"), 0) + 1
        print("\nUsage log totals:")
        for tool, count in sorted(by_tool.items()):
            print(f"  {tool}: {count}")

    fail_count = sum(1 for _, _, s in rows if s == "FAIL")
    print(f"\n{len(rows) - fail_count}/{len(rows)} checks passed.")
    if fail_count:
        sys.exit(1)
