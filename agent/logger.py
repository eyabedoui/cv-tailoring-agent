
"""
JSONL logger for the CV-tailoring agent.

Records:
1. Tool execution events.
2. Human approval checkpoint events.
3. Agent stop events.

Each event is stored as one JSON line.
"""

import json
import os
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
        return [
            redact_sensitive_data(item)
            for item in value
        ]

    return value


class AgentLogger:
    def __init__(self, log_dir=None, run_id=None):
        """
        Initialize the logger.

        Each run gets a separate JSONL file.
        log_dir defaults to the CV_AGENT_LOG_DIR env var, then "logs/".
        """
        if log_dir is None:
            log_dir = os.environ.get("CV_AGENT_LOG_DIR", "logs")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.run_id = run_id or str(uuid.uuid4())

        self.log_file = self.log_dir / f"{self.run_id}.jsonl"

        # Running totals updated by each log_step call.
        self._total_tokens_in = 0
        self._total_tokens_out = 0

    def _write_event(self, event):
        """Append one JSON event to the run's log file."""

        safe_event = redact_sensitive_data(event)

        with self.log_file.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(
                    safe_event,
                    ensure_ascii=False,
                    default=str,
                )
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

        self._total_tokens_in += tokens_in
        self._total_tokens_out += tokens_out

        from agent.config import PRICE_PER_MTOK_INPUT, PRICE_PER_MTOK_OUTPUT
        cost_usd = (
            tokens_in / 1_000_000 * PRICE_PER_MTOK_INPUT
            + tokens_out / 1_000_000 * PRICE_PER_MTOK_OUTPUT
        )

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
            "cost_usd": cost_usd,
        }

        self._write_event(event)

    def log_checkpoint(self, step, review_text, approved, timed_out=False):
        """
        Record the exact human review and approval decision.
        """

        if timed_out:
            decision = "timeout"
        else:
            decision = "approved" if approved else "rejected"

        event = {
            "event": "human_checkpoint",
            "run_id": self.run_id,
            "step": step,
            "review_text": review_text,
            "approved": approved,
            "decision": decision,
            "timed_out": timed_out,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._write_event(event)

    def log_stop(
        self,
        step,
        stop_reason,
        tokens_in=0,
        tokens_out=0,
        total_ms=0.0,
    ):
        """Record why the agent stopped, with per-task cost and time totals."""

        from agent.config import PRICE_PER_MTOK_INPUT, PRICE_PER_MTOK_OUTPUT

        total_tokens_in = self._total_tokens_in + tokens_in
        total_tokens_out = self._total_tokens_out + tokens_out
        total_cost_usd = (
            total_tokens_in / 1_000_000 * PRICE_PER_MTOK_INPUT
            + total_tokens_out / 1_000_000 * PRICE_PER_MTOK_OUTPUT
        )

        event = {
            "event": "stop",
            "run_id": self.run_id,
            "step": step,
            "stop_reason": stop_reason,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_cost_usd": total_cost_usd,
            "total_duration_ms": total_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._write_event(event)
