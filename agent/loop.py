
"""
ReAct agent loop for the CV-tailoring agent.

The loop:
1. Asks the model for a decision.
2. Executes tools.
3. Records tool executions.
4. Checks stop rules.
5. Requires human approval before submission.
"""

import json
import time

from datetime import datetime, timezone

from agent.stop_rule import should_stop
from agent.logger import AgentLogger
from agent.checkpoint import HumanApprovalCheckpoint
from agent.prompts import SYSTEM_PROMPT
from agent.tools.registry import TOOL_SCHEMAS, execute_tool
from agent.errors import (
    make_error, is_error,
    INVALID_ARGUMENTS, UNKNOWN_TOOL, BAD_RESPONSE,
)


class AgentLoop:
    def __init__(self, model, logger=None, checkpoint=None, on_step=None):
        self.model = model
        self.tools = TOOL_SCHEMAS
        self.logger = logger or AgentLogger()
        self.checkpoint = checkpoint or HumanApprovalCheckpoint()
        self.on_step = on_step

    def _fire_on_step(self, event: dict) -> None:
        """Call on_step callback, silently ignoring any exception it raises."""
        if self.on_step is None:
            return
        try:
            self.on_step(event)
        except Exception:
            pass

    def run(self, initial_messages=None, state=None):
        run_start = time.perf_counter()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        if initial_messages:
            messages.extend(initial_messages)

        # Per-turn loop control counters — always fresh each run.
        loop_state = {
            "step_count": 0,
            "match_score": None,
            "identical_call_count": 0,
            "user_rejected": False,
            "done": False,
            "checkpoint_timed_out": False,
        }

        previous_call = None

        # Workflow information collected (or carried in) during the run.
        job = None
        master_cv = None
        tailored_cv = None
        cover_letter = None

        # Initialise from provided state; per-turn counters always reset above.
        if state:
            job = state.get("job")
            master_cv = state.get("master_cv")
            tailored_cv = state.get("tailored_cv")
            cover_letter = state.get("cover_letter")

        def _ws():
            return {
                "job": job,
                "master_cv": master_cv,
                "tailored_cv": tailored_cv,
                "cover_letter": cover_letter,
            }

        while True:
            response = self.model.call_model(messages, self.tools)

            # --- malformed response guard ---
            if not isinstance(response, dict):
                loop_state["step_count"] += 1
                error_result = make_error(
                    BAD_RESPONSE,
                    "Model response was not a dictionary.",
                )
                self.logger.log_step(
                    step=loop_state["step_count"],
                    tool_name="(none)",
                    input_data={},
                    output_data=error_result,
                    start_time=datetime.now(timezone.utc).isoformat(),
                    duration_ms=0.0,
                )
                messages.append({
                    "role": "tool",
                    "name": "(none)",
                    "content": _wrap(error_result),
                })
                stop, reason = should_stop(loop_state)
                if stop:
                    self.logger.log_stop(step=loop_state["step_count"], stop_reason=reason)
                    return _stop_result(None, reason, loop_state["step_count"], messages, _ws())
                continue

            response_type = response.get("type")

            if response_type == "final":
                answer = response.get("content", "")
                loop_state["done"] = True

                messages.append({
                    "role": "assistant",
                    "content": answer,
                })

                usage = response.get("usage", {})
                tokens_in = usage.get("input_tokens", 0)
                tokens_out = usage.get("output_tokens", 0)

                _, reason = should_stop(loop_state)

                total_ms = (time.perf_counter() - run_start) * 1000

                self.logger.log_stop(
                    step=loop_state["step_count"],
                    stop_reason=reason,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    total_ms=total_ms,
                )

                return {
                    "answer": answer,
                    "stop_reason": reason,
                    "step_count": loop_state["step_count"],
                    "messages": messages,
                    "state": _ws(),
                }

            if response_type != "tool_call":
                # Unsupported type — treat as bad response, count as a step.
                loop_state["step_count"] += 1
                error_result = make_error(
                    BAD_RESPONSE,
                    f"Unsupported model response type: {response_type!r}.",
                )
                self.logger.log_step(
                    step=loop_state["step_count"],
                    tool_name="(none)",
                    input_data={},
                    output_data=error_result,
                    start_time=datetime.now(timezone.utc).isoformat(),
                    duration_ms=0.0,
                )
                messages.append({
                    "role": "tool",
                    "name": "(none)",
                    "content": _wrap(error_result),
                })
                stop, reason = should_stop(loop_state)
                if stop:
                    self.logger.log_stop(step=loop_state["step_count"], stop_reason=reason)
                    return _stop_result(None, reason, loop_state["step_count"], messages, _ws())
                continue

            tool_name = response.get("tool_name")
            arguments = response.get("arguments", {})

            if not isinstance(arguments, dict):
                # Non-dict arguments — bad response, count as a step.
                loop_state["step_count"] += 1
                error_result = make_error(
                    BAD_RESPONSE,
                    "Tool arguments must be a dictionary.",
                )
                self.logger.log_step(
                    step=loop_state["step_count"],
                    tool_name=tool_name or "(none)",
                    input_data={},
                    output_data=error_result,
                    start_time=datetime.now(timezone.utc).isoformat(),
                    duration_ms=0.0,
                )
                messages.append({
                    "role": "tool",
                    "name": tool_name or "(none)",
                    "content": _wrap(error_result),
                })
                stop, reason = should_stop(loop_state)
                if stop:
                    self.logger.log_stop(step=loop_state["step_count"], stop_reason=reason)
                    return _stop_result(None, reason, loop_state["step_count"], messages, _ws())
                continue

            if tool_name == "submit_application":
                # Validate prerequisites before going to the checkpoint.
                missing_prereqs = not all([
                    job,
                    master_cv is not None,
                    tailored_cv is not None,
                    cover_letter is not None,
                ])
                job_id = arguments.get("job_id")
                id_mismatch = job is not None and job_id != job.get("job_id")

                if missing_prereqs or id_mismatch:
                    loop_state["step_count"] += 1
                    if id_mismatch:
                        msg = (
                            "Submission job ID does not match the reviewed job. "
                            f"Expected {job.get('job_id')!r}, got {job_id!r}."
                        )
                    else:
                        msg = (
                            "Cannot request submission approval: "
                            "job, master CV, tailored CV, and cover letter "
                            "must all be available first."
                        )
                    error_result = make_error(INVALID_ARGUMENTS, msg)
                    self.logger.log_step(
                        step=loop_state["step_count"],
                        tool_name=tool_name,
                        input_data=arguments,
                        output_data=error_result,
                        start_time=datetime.now(timezone.utc).isoformat(),
                        duration_ms=0.0,
                    )
                    messages.append({
                        "role": "assistant",
                        "content": json.dumps({
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "arguments": arguments,
                        }),
                    })
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "content": _wrap(error_result),
                    })
                    stop, reason = should_stop(loop_state)
                    if stop:
                        self.logger.log_stop(step=loop_state["step_count"], stop_reason=reason)
                        return _stop_result(None, reason, loop_state["step_count"], messages, _ws())
                    continue

                # The model's submission request counts as a step.
                loop_state["step_count"] += 1

                # Display the review and obtain the human decision.
                approved = self.checkpoint.request_approval(
                    job_title=job.get("title", "Unknown job"),
                    company=job.get("company", "Unknown company"),
                    job_id=job_id,
                    master_cv=master_cv,
                    tailored_cv=tailored_cv,
                    cover_letter=cover_letter,
                )

                timed_out = getattr(self.checkpoint, "timed_out", False)

                self.logger.log_checkpoint(
                    step=loop_state["step_count"],
                    review_text=self.checkpoint.last_review_text,
                    approved=approved,
                    timed_out=timed_out,
                )

                self._fire_on_step({
                    "step": loop_state["step_count"],
                    "tool": "human_checkpoint",
                    "arguments": {"job_id": job_id},
                    "result": {"approved": approved, "timed_out": timed_out},
                })

                if timed_out:
                    loop_state["checkpoint_timed_out"] = True
                    _, reason = should_stop(loop_state)
                    self.logger.log_stop(step=loop_state["step_count"], stop_reason=reason)
                    return _stop_result(
                        "Checkpoint timed out; submission cancelled.",
                        reason,
                        loop_state["step_count"],
                        messages,
                        _ws(),
                    )

                if not approved:
                    loop_state["user_rejected"] = True
                    _, reason = should_stop(loop_state)

                    self.logger.log_stop(
                        step=loop_state["step_count"],
                        stop_reason=reason,
                    )

                    return _stop_result(
                        "Application submission was rejected by the user.",
                        reason,
                        loop_state["step_count"],
                        messages,
                        _ws(),
                    )

            # Record the tool-call decision.
            # For submission, the step was already counted above.
            if tool_name != "submit_application":
                loop_state["step_count"] += 1

            messages.append({
                "role": "assistant",
                "content": json.dumps({
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "arguments": arguments,
                }),
            })

            current_call = {
                "tool_name": tool_name,
                "arguments": arguments,
            }

            if current_call == previous_call:
                loop_state["identical_call_count"] += 1
            else:
                loop_state["identical_call_count"] = 1

            previous_call = current_call

            start_timestamp = datetime.now(timezone.utc).isoformat()
            start_counter = time.perf_counter()

            result = execute_tool(tool_name, arguments)

            duration_ms = (time.perf_counter() - start_counter) * 1000

            # Only update state from successful (non-error) results.
            if not is_error(result):
                if tool_name == "read_job_posting":
                    job = result

                elif tool_name == "read_master_cv":
                    master_cv = result.get("text")

                elif tool_name == "save_tailored_cv":
                    kind = arguments.get("kind")
                    if kind == "cv":
                        tailored_cv = arguments.get("text")
                    elif kind == "cover_letter":
                        cover_letter = arguments.get("text")

                if tool_name == "match_skills":
                    score = result.get("score", result.get("match_score"))
                    if score is not None:
                        loop_state["match_score"] = score

            usage = response.get("usage", {})
            tokens_in = usage.get("input_tokens", 0)
            tokens_out = usage.get("output_tokens", 0)

            self.logger.log_step(
                step=loop_state["step_count"],
                tool_name=tool_name,
                input_data=arguments,
                output_data=result,
                start_time=start_timestamp,
                duration_ms=duration_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )

            self._fire_on_step({
                "step": loop_state["step_count"],
                "tool": tool_name,
                "arguments": arguments,
                "result": result,
            })

            messages.append({
                "role": "tool",
                "name": tool_name,
                "content": _wrap(result),
            })

            stop, reason = should_stop(loop_state)

            if stop:
                total_ms = (time.perf_counter() - run_start) * 1000
                self.logger.log_stop(
                    step=loop_state["step_count"],
                    stop_reason=reason,
                    total_ms=total_ms,
                )

                return _stop_result(None, reason, loop_state["step_count"], messages, _ws())


def _wrap(result) -> str:
    """Wrap a tool result in an untrusted tag (delegates to untrusted module)."""
    from agent.untrusted import wrap_untrusted
    return wrap_untrusted(result)


def _stop_result(answer, reason, step_count, messages, workflow_state=None):
    return {
        "answer": answer,
        "stop_reason": reason,
        "step_count": step_count,
        "messages": messages,
        "state": workflow_state if workflow_state is not None else {},
    }
