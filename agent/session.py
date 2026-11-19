"""
Session layer for the CV-tailoring agent chat interface.

Wraps AgentLoop to support multi-turn conversations with:
- Persistent message history across turns
- History trimming to avoid context overflow
- Session-level step cap
- Clean ModelUnavailableError handling
"""

from agent.config import MAX_STEPS_PER_SESSION, MAX_HISTORY_MESSAGES
from agent.loop import AgentLoop
from agent.model import ModelUnavailableError


class Session:
    def __init__(self, model, checkpoint, logger=None, on_step=None):
        self._model = model
        self._checkpoint = checkpoint
        self._logger = logger
        self._on_step = on_step
        self._history = []        # Non-system messages from prior turns
        self._workflow_state = None  # Carry job/cv state between turns
        self._total_steps = 0     # Cumulative steps across all turns

    def send(self, user_text: str) -> dict:
        """
        Send a user message and run the agent.

        Returns the loop result dict (answer, stop_reason, step_count, state),
        or a synthetic dict with stop_reason "session_limit" / "model_unavailable".
        """
        if self._total_steps >= MAX_STEPS_PER_SESSION:
            return {
                "answer": "Session step limit reached.",
                "stop_reason": "session_limit",
                "step_count": 0,
                "state": self._workflow_state or {},
            }

        self._history.append({"role": "user", "content": user_text})

        agent = AgentLoop(
            model=self._model,
            checkpoint=self._checkpoint,
            logger=self._logger,
            on_step=self._on_step,
        )

        try:
            result = agent.run(
                initial_messages=list(self._history),
                state=self._workflow_state,
            )
        except ModelUnavailableError as exc:
            self._history.pop()  # Remove the failed user turn
            return {
                "answer": str(exc),
                "stop_reason": "model_unavailable",
                "step_count": 0,
                "state": self._workflow_state or {},
            }

        self._workflow_state = result.get("state")
        self._total_steps += result.get("step_count", 0)

        # Rebuild history from run output, dropping the system message.
        self._history = [
            m for m in result.get("messages", [])
            if m.get("role") != "system"
        ]
        self._trim_history()

        return result

    def _trim_history(self) -> None:
        """
        Trim history to MAX_HISTORY_MESSAGES.

        After trimming, the first message must be a user message.
        Drop oldest messages until within the limit and starts with user.
        """
        while len(self._history) > MAX_HISTORY_MESSAGES:
            self._history.pop(0)

        while self._history and self._history[0].get("role") != "user":
            self._history.pop(0)

    def reset(self) -> None:
        """Reset history, workflow state, and step counter."""
        self._history = []
        self._workflow_state = None
        self._total_steps = 0
