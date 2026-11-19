"""
Queue-based approval checkpoint for the chat interface.

The host (UI thread) calls submit_decision(approved) after displaying the review;
the agent loop waits in request_approval() until a decision arrives or times out.
"""

import queue
import threading

from agent.checkpoint import HumanApprovalCheckpoint
from agent.config import CHECKPOINT_TIMEOUT_SECONDS


class ChatCheckpoint(HumanApprovalCheckpoint):
    def __init__(self, present_fn, timeout_seconds=CHECKPOINT_TIMEOUT_SECONDS):
        super().__init__(timeout_seconds=timeout_seconds)
        self._present_fn = present_fn
        self._lock = threading.Lock()
        self._pending = False
        self._current_queue = None

    def request_approval(
        self,
        job_title,
        company,
        job_id,
        master_cv,
        tailored_cv,
        cover_letter,
    ) -> bool:
        """
        Build and present the review, then block until submit_decision() is called.

        Returns True (approved) or False (rejected / timed out).
        """
        self.timed_out = False

        review_text = self.build_review_text(
            job_title=job_title,
            company=company,
            job_id=job_id,
            master_cv=master_cv,
            tailored_cv=tailored_cv,
            cover_letter=cover_letter,
        )
        self.last_review_text = review_text

        with self._lock:
            self._current_queue = queue.Queue()
            self._pending = True

        self._present_fn(review_text)

        try:
            approved = self._current_queue.get(timeout=self.timeout_seconds)
        except queue.Empty:
            self.timed_out = True
            approved = False
        finally:
            with self._lock:
                self._pending = False
                self._current_queue = None

        self.last_decision = approved
        return approved

    def submit_decision(self, approved: bool) -> None:
        """
        Submit an approval decision from the UI thread.

        Raises TypeError if approved is not exactly True or False.
        Late decisions (no request pending) are silently ignored.
        """
        if not isinstance(approved, bool):
            raise TypeError(
                f"submit_decision() requires a bool, got {type(approved).__name__!r}."
            )

        with self._lock:
            if not self._pending:
                return  # Ignore late decisions
            q = self._current_queue

        if q is not None:
            q.put(approved)
