
import json

from agent.logger import AgentLogger
from agent.fake_model import FakeModel
from agent.loop import AgentLoop
from agent.checkpoint import HumanApprovalCheckpoint


def read_events(log_file):
    with log_file.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file]


def test_logger_creates_jsonl_file(tmp_path):
    logger = AgentLogger(log_dir=tmp_path, run_id="test_run")

    assert logger.log_file.exists() is False

    logger.log_stop(step=0, stop_reason="done")

    assert logger.log_file.exists()


def test_logger_records_tool_call(tmp_path):
    logger = AgentLogger(log_dir=tmp_path, run_id="test_run")

    logger.log_step(
        step=1,
        tool_name="read_master_cv",
        input_data={},
        output_data={"text": "Sample CV"},
        start_time="2026-11-13T12:00:00+00:00",
        duration_ms=12.5,
        tokens_in=100,
        tokens_out=50,
    )

    events = read_events(logger.log_file)

    assert len(events) == 1
    assert events[0]["event"] == "tool_call"
    assert events[0]["run_id"] == "test_run"
    assert events[0]["step"] == 1
    assert events[0]["tool_name"] == "read_master_cv"
    assert events[0]["duration_ms"] == 12.5
    assert events[0]["tokens_in"] == 100
    assert events[0]["tokens_out"] == 50


def test_logger_records_stop_reason(tmp_path):
    logger = AgentLogger(log_dir=tmp_path, run_id="test_run")

    logger.log_stop(step=3, stop_reason="max_steps")

    events = read_events(logger.log_file)

    assert events[-1]["event"] == "stop"
    assert events[-1]["stop_reason"] == "max_steps"
    assert events[-1]["step"] == 3


def test_logger_appends_multiple_events(tmp_path):
    logger = AgentLogger(log_dir=tmp_path, run_id="test_run")

    logger.log_step(
        step=1,
        tool_name="read_master_cv",
        input_data={},
        output_data={"text": "CV"},
        start_time="2026-11-13T12:00:00+00:00",
        duration_ms=10,
    )

    logger.log_stop(step=1, stop_reason="done")

    events = read_events(logger.log_file)

    assert len(events) == 2
    assert events[0]["event"] == "tool_call"
    assert events[1]["event"] == "stop"


def test_logger_redacts_sensitive_keys(tmp_path):
    logger = AgentLogger(log_dir=tmp_path, run_id="test_run")

    logger.log_step(
        step=1,
        tool_name="example_tool",
        input_data={"api_key": "secret-value"},
        output_data={"result": "success"},
        start_time="2026-11-13T12:00:00+00:00",
        duration_ms=5,
    )

    events = read_events(logger.log_file)

    assert events[0]["input"]["api_key"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# Item 4: tokens, cost and task timing
# ---------------------------------------------------------------------------

def test_logger_records_cost_usd_in_step(tmp_path):
    logger = AgentLogger(log_dir=tmp_path, run_id="cost_test")

    logger.log_step(
        step=1,
        tool_name="read_master_cv",
        input_data={},
        output_data={},
        start_time="2026-11-14T10:00:00+00:00",
        duration_ms=5.0,
        tokens_in=200,
        tokens_out=100,
    )

    events = read_events(logger.log_file)
    assert "cost_usd" in events[0]
    assert isinstance(events[0]["cost_usd"], float)


def test_stop_event_has_total_fields(tmp_path):
    logger = AgentLogger(log_dir=tmp_path, run_id="totals_test")

    logger.log_step(
        step=1,
        tool_name="read_master_cv",
        input_data={},
        output_data={},
        start_time="2026-11-14T10:00:00+00:00",
        duration_ms=5.0,
        tokens_in=100,
        tokens_out=50,
    )

    logger.log_stop(
        step=1,
        stop_reason="done",
        tokens_in=20,
        tokens_out=10,
        total_ms=250.0,
    )

    events = read_events(logger.log_file)
    stop = events[-1]

    assert stop["total_tokens_in"] == 120   # 100 from step + 20 from final
    assert stop["total_tokens_out"] == 60   # 50 from step + 10 from final
    assert stop["total_duration_ms"] == 250.0
    assert "total_cost_usd" in stop


def test_usage_flows_through_fake_model(tmp_path):
    """FakeModel responses with 'usage' key reach the logger."""

    model = FakeModel([
        {
            "type": "tool_call",
            "tool_name": "read_master_cv",
            "arguments": {},
            "usage": {"input_tokens": 50, "output_tokens": 25},
        },
        {
            "type": "final",
            "content": "Done.",
            "usage": {"input_tokens": 30, "output_tokens": 15},
        },
    ])

    logger = AgentLogger(log_dir=tmp_path, run_id="usage_test")
    agent = AgentLoop(
        model,
        checkpoint=HumanApprovalCheckpoint(auto_approve=True),
        logger=logger,
    )
    agent.run()

    events = read_events(logger.log_file)

    tool_event = next(e for e in events if e["event"] == "tool_call")
    assert tool_event["tokens_in"] == 50
    assert tool_event["tokens_out"] == 25

    stop_event = next(e for e in events if e["event"] == "stop")
    # 50+30 input, 25+15 output
    assert stop_event["total_tokens_in"] == 80
    assert stop_event["total_tokens_out"] == 40
