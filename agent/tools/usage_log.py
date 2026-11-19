"""
Append-only usage log for real web tool calls.

Each entry is a JSON line written to sandbox/usage_log.jsonl.
Logging failures are swallowed so they never abort the agent.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from agent.config import SANDBOX_DIR

_LOG_FILENAME = "usage_log.jsonl"


def log_usage(
    tool: str,
    host: str,
    status: str,
    detail: str = "",
    _log_path: Path | None = None,
) -> None:
    """
    Append one usage entry to the log.

    Parameters:
      tool     – tool name (find_jobs, read_job_posting, submit_application)
      host     – target host (e.g. www.keejob.com)
      status   – outcome string (success, error code, …)
      detail   – optional extra context
      _log_path – override path; for tests
    """
    log_path = _log_path if _log_path is not None else Path(SANDBOX_DIR) / _LOG_FILENAME
    entry: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "host": host,
        "status": status,
    }
    if detail:
        entry["detail"] = detail
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass
