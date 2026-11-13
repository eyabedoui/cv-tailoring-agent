
import pytest
import json
from agent.logger import AgentLogger
from agent.fake_model import FakeModel
from agent.loop import AgentLoop


def test_agent_loop_executes_tool_and_returns_final_answer():
    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_job_posting",
            "arguments": {"url": "mock://jobs/job_001"},
        },
        {
            "type": "final",
            "content": "The job posting was successfully read.",
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    assert result["answer"] == "The job posting was successfully read."
    assert result["stop_reason"] == "done"
    assert result["step_count"] == 1


def test_agent_loop_adds_tool_result_as_untrusted_data():
    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "final",
            "content": "CV read successfully.",
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    tool_messages = [
        message for message in result["messages"]
        if message["role"] == "tool"
    ]

    assert len(tool_messages) == 1
    assert 'untrusted="true"' in tool_messages[0]["content"]


def test_agent_loop_continues_when_match_score_is_above_threshold():
    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "match_skills",
            "arguments": {
                "cv_text": "Sample CV",
                "job": {"requirements": ["Python"]},
            },
        },
        {
            "type": "final",
            "content": "Skill matching completed.",
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    # The stub returns 0.5, above the 0.25 threshold.
    assert result["stop_reason"] == "done"
    assert result["step_count"] == 1
    assert result["answer"] == "Skill matching completed."


def test_agent_loop_stops_when_match_score_is_below_threshold(monkeypatch):
    # Simulate a poor skill-match result.
    def fake_low_match(tool_name, arguments):
        return {
            "matched": [],
            "missing": ["Python", "Machine learning"],
            "score": 0.1,
        }

    monkeypatch.setattr("agent.loop.execute_tool", fake_low_match)

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "match_skills",
            "arguments": {
                "cv_text": "Sample CV",
                "job": {
                    "requirements": ["Python", "Machine learning"]
                },
            },
        },
    ])

    agent = AgentLoop(model)
    result = agent.run()

    assert result["stop_reason"] == "no_match"
    assert result["step_count"] == 1
    assert result["answer"] is None


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
    assert result["step_count"] == 3


def test_agent_loop_blocks_submission_without_approval():
    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "submit_application",
            "arguments": {
                "cv_path": "cv.txt",
                "cover_letter_path": "cover.txt",
                "job_id": "job_001",
            },
        },
    ])

    agent = AgentLoop(model)

    with pytest.raises(PermissionError, match="Human approval"):
        agent.run()

def test_agent_loop_automatically_logs_tool_calls_and_stop(tmp_path):
    logger = AgentLogger(
        log_dir=tmp_path,
        run_id="integration_test",
    )

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
        },
        {
            "type": "final",
            "content": "CV read successfully.",
        },
    ])

    agent = AgentLoop(model, logger=logger)
    result = agent.run()

    with logger.log_file.open("r", encoding="utf-8") as file:
        events = [json.loads(line) for line in file]

    assert result["stop_reason"] == "done"
    assert len(events) == 2

    assert events[0]["event"] == "tool_call"
    assert events[0]["tool_name"] == "read_master_cv"
    assert events[0]["step"] == 1

    assert events[1]["event"] == "stop"
    assert events[1]["stop_reason"] == "done"
