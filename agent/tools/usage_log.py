"""
Append-only usage log for real web tool calls.

Each entry is a JSON line written to logs/tool_usage.jsonl by default.
The directory is controlled by the CV_AGENT_LOG_DIR environment variable
(default: "logs").  Logging failures are swallowed so they never abort the agent.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

_LOG_FILENAME = "tool_usage.jsonl"


def _default_log_path() -> Path:
    log_dir = os.environ.get("CV_AGENT_LOG_DIR", "logs")
    return Path(log_dir) / _LOG_FILENAME


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
    log_path = _log_path if _log_path is not None else _default_log_path()
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
