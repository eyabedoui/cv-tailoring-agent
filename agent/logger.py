
"""
JSONL logger for the CV-tailoring agent.

Each tool call produces one JSONL event.
The end of each run produces a separate stop event.
"""

import json
import re
import uuid

from datetime import datetime, timezone
from pathlib import Path


SENSITIVE_KEY_PATTERN = re.compile(
    r"api[_-]?key|password|secret|authorization|"
    r"access[_-]?token|refresh[_-]?token",
    re.IGNORECASE,
)


def redact_sensitive_data(value):
    """
    Recursively redact values stored under sensitive dictionary keys.
    """
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if SENSITIVE_KEY_PATTERN.search(str(key))
                else redact_sensitive_data(item)
            )
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]

    return value


class AgentLogger:
    def __init__(self, log_dir="logs", run_id=None):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.run_id = run_id or str(uuid.uuid4())
        self.log_file = self.log_dir / f"{self.run_id}.jsonl"

    def _write_event(self, event):
        """Append one JSON event to the run's log file."""
        safe_event = redact_sensitive_data(event)

        with self.log_file.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(safe_event, ensure_ascii=False, default=str)
                + "\n"
            )

    def log_step(
        self,
        step,
        tool_name,
        input_data,
        output_data,
        start_time,
        duration_ms,
        tokens_in=0,
        tokens_out=0,
    ):
        """Record one tool execution."""
        event = {
            "event": "tool_call",
            "run_id": self.run_id,
            "step": step,
            "tool_name": tool_name,
            "input": input_data,
            "output": output_data,
            "start_time": start_time,
            "duration_ms": duration_ms,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }

        self._write_event(event)

    def log_stop(self, step, stop_reason):
        """Record why the agent stopped."""
        event = {
            "event": "stop",
            "run_id": self.run_id,
            "step": step,
            "stop_reason": stop_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._write_event(event)
