
import pytest

from agent.tools.registry import (
    TOOL_FUNCTIONS,
    TOOL_SCHEMAS,
    execute_tool,
)
from sandbox.portal import Portal
import agent.tools.writes as _writes_mod


def test_registry_contains_six_tools():
    assert len(TOOL_FUNCTIONS) == 6


def test_all_six_tool_schemas_are_available():
    names = {tool["name"] for tool in TOOL_SCHEMAS}

    assert names == {
        "read_job_posting",
        "read_master_cv",
        "match_skills",
        "check_format",
        "save_tailored_cv",
        "submit_application",
    }


def test_read_job_posting():
    result = execute_tool(
        "read_job_posting",
        {"url": "mock://jobs/job_001"},
    )

    assert result["job_id"] == "job_001"
    assert result["title"] == "Junior AI Engineer"
    assert isinstance(result["requirements"], list)


def test_read_master_cv():
    result = execute_tool("read_master_cv", {})

    assert "Python" in result["text"]
    assert "skills" in result["sections"]


def test_match_skills():
    result = execute_tool(
        "match_skills",
        {
            "cv_text": "Python and SQL",
            "job": {"requirements": ["Python", "SQL"]},
        },
    )

    assert 0 <= result["score"] <= 1
    assert "matched" in result
    assert "missing" in result


def test_check_format():
    result = execute_tool(
        "check_format",
        {"cv_text": "Sample CV"},
    )

    assert result["ok"] is True
    assert result["issues"] == []


def test_save_tailored_cv(tmp_path, monkeypatch):
    monkeypatch.setattr(_writes_mod, "_portal", Portal(sandbox_dir=str(tmp_path)))
    result = execute_tool(
        "save_tailored_cv",
        {
            "text": "Tailored CV",
            "job_id": "job_001",
            "kind": "cv",
        },
    )

    assert result["saved"] is True
    assert "job_001" in result["path"]


def test_save_tailored_cv_rejects_invalid_kind():
    # Now returns make_error instead of raising (error contract, Item 2).
    result = execute_tool(
        "save_tailored_cv",
        {
            "text": "Sample",
            "job_id": "job_001",
            "kind": "invalid",
        },
    )
    assert result["error"] == "INVALID_ARGUMENTS"


def test_submit_application(tmp_path, monkeypatch):
    monkeypatch.setattr(_writes_mod, "_portal", Portal(sandbox_dir=str(tmp_path)))
    result = execute_tool(
        "submit_application",
        {
            "cv_path": "sandbox/output/cv_job_001.md",
            "cover_letter_path": "sandbox/output/cover_letter_job_001.md",
            "job_id": "job_001",
        },
    )

    assert result["status"] == "submitted"
    assert result["application_id"] == "app_job_001"


def test_unknown_tool_is_rejected():
    # Now returns make_error instead of raising (error contract, Item 2).
    result = execute_tool("unknown_tool", {})
    assert result["error"] == "UNKNOWN_TOOL"
