
from agent.fake_model import FakeModel
from agent.loop import AgentLoop


def test_agent_loop_executes_tool_and_returns_final_answer():
    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "final",
            "content": "The CV has been read.",
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    assert result["answer"] == "The CV has been read."
    assert result["stop_reason"] == "done"


def test_agent_loop_wraps_tool_results_as_untrusted_data():
    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "final",
            "content": "Done.",
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    messages = result["messages"]

    assert any(
        '<tool_result untrusted="true">' in message.get("content", "")
        for message in messages
    )


def test_agent_loop_continues_when_match_score_is_above_threshold():
    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "match_skills",
            "arguments": {
                "cv_text": "Python, SQL",
                "job": {"title": "Junior AI Engineer"},
            },
        },
        {
            "type": "final",
            "content": "Matching completed.",
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    assert result["answer"] == "Matching completed."
    assert result["stop_reason"] == "done"


def test_agent_loop_stops_when_match_score_is_too_low(monkeypatch):
    def fake_execute_tool(tool_name, arguments):
        if tool_name == "match_skills":
            return {
                "match_score": 0.10,
                "matched_skills": [],
                "missing_skills": ["Python"],
            }

        return {}

    monkeypatch.setattr(
        "agent.loop.execute_tool",
        fake_execute_tool,
    )

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "match_skills",
            "arguments": {
                "cv_text": "Java",
                "job": {"title": "Junior AI Engineer"},
            },
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    assert result["stop_reason"] == "no_match"
    assert result["step_count"] == 1


def test_agent_loop_stops_after_three_identical_calls():
    repeated_call = {
        "type": "tool_call",
        "tool_name": "read_master_cv",
        "arguments": {},
    }

    model = FakeModel([
        repeated_call,
        repeated_call,
        repeated_call,
    ])

    agent = AgentLoop(model)
    result = agent.run()

    assert result["stop_reason"] == "repeated_call"


def test_agent_loop_blocks_submission_when_user_rejects(
    monkeypatch,
    tmp_path,
):
    from agent.checkpoint import HumanApprovalCheckpoint
    from agent.logger import AgentLogger
    from agent.tools.registry import execute_tool as real_execute_tool

    executed_tools = []

    def tracking_execute_tool(tool_name, arguments):
        executed_tools.append(tool_name)
        return real_execute_tool(tool_name, arguments)

    monkeypatch.setattr(
        "agent.loop.execute_tool",
        tracking_execute_tool,
    )

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_job_posting",
            "arguments": {
                "url": "mock://jobs/job_001",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Tailored CV content",
                "job_id": "job_001",
                "kind": "cv",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Dear Hiring Manager.",
                "job_id": "job_001",
                "kind": "cover_letter",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "submit_application",
            "arguments": {
                "cv_path": "sandbox/output/job_001_cv.txt",
                "cover_letter_path": "sandbox/output/job_001_cover_letter.txt",
                "job_id": "job_001",
            },
        },
    ])

    checkpoint = HumanApprovalCheckpoint(auto_reject=True)

    logger = AgentLogger(
        log_dir=tmp_path,
        run_id="rejection_test",
    )

    agent = AgentLoop(
        model,
        logger=logger,
        checkpoint=checkpoint,
    )

    result = agent.run()

    assert result["stop_reason"] == "user_rejected"
    assert "submit_application" not in executed_tools
    assert checkpoint.last_decision is False

def test_agent_loop_submits_application_after_user_approves(
    monkeypatch,
    tmp_path,
):
    from agent.checkpoint import HumanApprovalCheckpoint
    from agent.logger import AgentLogger
    from agent.tools.registry import execute_tool as real_execute_tool

    executed_tools = []

    def tracking_execute_tool(tool_name, arguments):
        executed_tools.append(tool_name)
        return real_execute_tool(tool_name, arguments)

    monkeypatch.setattr(
        "agent.loop.execute_tool",
        tracking_execute_tool,
    )

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_job_posting",
            "arguments": {
                "url": "mock://jobs/job_001",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Tailored CV content",
                "job_id": "job_001",
                "kind": "cv",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "save_tailored_cv",
            "arguments": {
                "text": "Dear Hiring Manager.",
                "job_id": "job_001",
                "kind": "cover_letter",
            },
        },
        {
            "type": "tool_call",
            "tool_name": "submit_application",
            "arguments": {
                "cv_path": "sandbox/output/job_001_cv.txt",
                "cover_letter_path": "sandbox/output/job_001_cover_letter.txt",
                "job_id": "job_001",
            },
        },
        {
            "type": "final",
            "content": "Application submitted successfully.",
        },
    ])

    checkpoint = HumanApprovalCheckpoint(auto_approve=True)

    logger = AgentLogger(
        log_dir=tmp_path,
        run_id="approval_test",
    )

    agent = AgentLoop(
        model,
        logger=logger,
        checkpoint=checkpoint,
    )

    result = agent.run()

    # Submission must actually be executed after approval.
    assert "submit_application" in executed_tools

    # The checkpoint must record approval.
    assert checkpoint.last_decision is True

    # The agent must continue and return the final response.
    assert result["answer"] == "Application submitted successfully."
    assert result["stop_reason"] == "done"

    # Verify that the approval decision was written to the log.
    import json

    log_file = tmp_path / "approval_test.jsonl"
    events = [
        json.loads(line)
        for line in log_file.read_text(encoding="utf-8").splitlines()
    ]

    checkpoint_events = [
        event for event in events
        if event["event"] == "human_checkpoint"
    ]

    assert len(checkpoint_events) == 1
    assert checkpoint_events[0]["approved"] is True
