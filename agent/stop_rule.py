
"""
Agent stop rules.

Definition of a step:
One step is one model decision that results in one tool call.
The human approval checkpoint and final answer do not count as steps.

The stop rule is evaluated after every tool call and before
the agent decides whether to continue.
"""

from agent.config import (
    MAX_STEPS,
    NO_MATCH_THRESHOLD,
    MAX_SAME_CALL_REPEATS,
)


def should_stop(state: dict) -> tuple[bool, str | None]:
    """
    Determine whether the agent must stop.

    Expected state keys:
        step_count: Number of model decisions/tool calls.
        match_score: Skill matching score (0 to 1), or None.
        identical_call_count: Number of consecutive identical calls.
        user_rejected: Whether the human rejected submission.
        done: Whether the workflow completed.

    Returns:
        (True, reason) if the agent must stop.
        (False, None) otherwise.
    """

    # 1. Human rejection has priority.
    if state.get("user_rejected", False):
        return True, "user_rejected"

    # 1b. Checkpoint timeout.
    if state.get("checkpoint_timed_out", False):
        return True, "checkpoint_timeout"

    # 2. Stop if the workflow is completed.
    if state.get("done", False):
        return True, "done"

    # 3. Stop when the maximum number of steps is reached.
    if state.get("step_count", 0) >= MAX_STEPS:
        return True, "max_steps"

    # 4. Stop when there is no sufficient skill match.
    match_score = state.get("match_score")

    if match_score is not None and match_score < NO_MATCH_THRESHOLD:
        return True, "no_match"

    # 5. Stop when the same call is repeated too many times.
    if state.get("identical_call_count", 0) >= MAX_SAME_CALL_REPEATS:
        return True, "repeated_call"

    # Otherwise, the agent can continue.
    return False, None
