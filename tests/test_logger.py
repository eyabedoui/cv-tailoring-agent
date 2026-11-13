
import json

from agent.logger import AgentLogger


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
