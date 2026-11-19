
"""
Tests for agent/tools/schemas.py and the pydantic validation layer in registry.py.
"""

import pytest
from pydantic import ValidationError

from agent.sites import own_job_url
from agent.tools.schemas import (
    ReadJobPostingIn,
    ReadMasterCvIn,
    MatchSkillsIn,
    CheckFormatIn,
    SaveTailoredCvIn,
    SubmitApplicationIn,
    TOOL_SCHEMA_MAP,
)
from agent.tools.registry import TOOL_SCHEMAS, execute_tool


# ---------------------------------------------------------------------------
# ReadJobPostingIn
# ---------------------------------------------------------------------------

def test_read_job_posting_in_accepts_own_site_url():
    m = ReadJobPostingIn(url=own_job_url("job_001"))
    assert m.url == own_job_url("job_001")


def test_read_job_posting_in_accepts_allowlisted_https_url():
    m = ReadJobPostingIn(url="https://www.tanitjobs.com/jobs/123")
    assert m.url == "https://www.tanitjobs.com/jobs/123"


def test_read_job_posting_in_rejects_wrong_prefix():
    # Non-allowlisted https URL is rejected at pydantic level.
    with pytest.raises(ValidationError) as exc_info:
        ReadJobPostingIn(url="https://example.com/jobs/job_001")
    assert "url" in str(exc_info.value)


def test_read_job_posting_in_rejects_bad_job_id_suffix():
    # own-site URL with invalid job_id (only 1 digit) is rejected.
    with pytest.raises(ValidationError):
        ReadJobPostingIn(url=own_job_url("job_1"))


def test_read_job_posting_in_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ReadJobPostingIn(url=own_job_url("job_001"), extra_field="x")


def test_read_job_posting_in_rejects_ftp_url():
    with pytest.raises(ValidationError):
        ReadJobPostingIn(url="ftp://www.tanitjobs.com/jobs/123")


# ---------------------------------------------------------------------------
# ReadMasterCvIn
# ---------------------------------------------------------------------------

def test_read_master_cv_in_accepts_empty():
    m = ReadMasterCvIn()
    assert m is not None


def test_read_master_cv_in_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ReadMasterCvIn(unexpected="value")


# ---------------------------------------------------------------------------
# MatchSkillsIn
# ---------------------------------------------------------------------------

def test_match_skills_in_accepts_valid():
    m = MatchSkillsIn(cv_text="Python developer", job={"requirements": ["Python"]})
    assert m.cv_text == "Python developer"


def test_match_skills_in_rejects_missing_requirements_key():
    with pytest.raises(ValidationError) as exc_info:
        MatchSkillsIn(cv_text="Python", job={"title": "Engineer"})
    assert "requirements" in str(exc_info.value)


def test_match_skills_in_rejects_non_list_requirements():
    with pytest.raises(ValidationError):
        MatchSkillsIn(cv_text="Python", job={"requirements": "Python"})


def test_match_skills_in_rejects_empty_cv_text():
    with pytest.raises(ValidationError):
        MatchSkillsIn(cv_text="", job={"requirements": ["Python"]})


def test_match_skills_in_rejects_cv_text_too_long():
    with pytest.raises(ValidationError):
        MatchSkillsIn(cv_text="x" * 20_001, job={"requirements": ["Python"]})


# ---------------------------------------------------------------------------
# CheckFormatIn
# ---------------------------------------------------------------------------

def test_check_format_in_accepts_valid():
    m = CheckFormatIn(cv_text="Some CV content")
    assert m.cv_text == "Some CV content"


def test_check_format_in_rejects_empty():
    with pytest.raises(ValidationError):
        CheckFormatIn(cv_text="")


# ---------------------------------------------------------------------------
# SaveTailoredCvIn
# ---------------------------------------------------------------------------

def test_save_tailored_cv_in_accepts_cv_kind():
    m = SaveTailoredCvIn(text="CV text", job_id="job_001", kind="cv")
    assert m.kind == "cv"


def test_save_tailored_cv_in_accepts_cover_letter_kind():
    m = SaveTailoredCvIn(text="Letter text", job_id="job_001", kind="cover_letter")
    assert m.kind == "cover_letter"


def test_save_tailored_cv_in_accepts_live_site_job_id():
    m = SaveTailoredCvIn(text="CV text", job_id="tanitjobs-a1b2c3d4", kind="cv")
    assert m.job_id == "tanitjobs-a1b2c3d4"


def test_save_tailored_cv_in_rejects_bad_kind():
    with pytest.raises(ValidationError):
        SaveTailoredCvIn(text="text", job_id="job_001", kind="resume")


def test_save_tailored_cv_in_rejects_bad_job_id():
    with pytest.raises(ValidationError) as exc_info:
        SaveTailoredCvIn(text="text", job_id="job_1", kind="cv")
    assert "job_id" in str(exc_info.value)


def test_save_tailored_cv_in_rejects_non_job_prefix():
    with pytest.raises(ValidationError):
        SaveTailoredCvIn(text="text", job_id="app_001", kind="cv")


# ---------------------------------------------------------------------------
# SubmitApplicationIn
# ---------------------------------------------------------------------------

def test_submit_application_in_accepts_valid():
    m = SubmitApplicationIn(
        cv_path="sandbox/output/cv_job_001.md",
        cover_letter_path="sandbox/output/cover_letter_job_001.md",
        job_id="job_001",
    )
    assert m.job_id == "job_001"


def test_submit_application_in_accepts_live_site_job_id():
    m = SubmitApplicationIn(
        cv_path="a.md",
        cover_letter_path="b.md",
        job_id="keejob-00000000",
    )
    assert m.job_id == "keejob-00000000"


def test_submit_application_in_rejects_bad_job_id():
    with pytest.raises(ValidationError):
        SubmitApplicationIn(
            cv_path="a.md",
            cover_letter_path="b.md",
            job_id="001",
        )


# ---------------------------------------------------------------------------
# TOOL_SCHEMA_MAP completeness
# ---------------------------------------------------------------------------

def test_tool_schema_map_has_seven_entries():
    assert len(TOOL_SCHEMA_MAP) == 7


def test_tool_schema_map_values_are_model_pairs():
    from pydantic import BaseModel
    for name, (in_cls, out_cls) in TOOL_SCHEMA_MAP.items():
        assert issubclass(in_cls, BaseModel), f"{name}: input not a BaseModel"
        assert issubclass(out_cls, BaseModel), f"{name}: output not a BaseModel"


# ---------------------------------------------------------------------------
# input_schema present in TOOL_SCHEMAS entries
# ---------------------------------------------------------------------------

def test_all_tool_schemas_have_input_schema():
    for entry in TOOL_SCHEMAS:
        assert "input_schema" in entry, f"{entry['name']} missing input_schema"
        schema = entry["input_schema"]
        assert isinstance(schema, dict), f"{entry['name']} input_schema is not a dict"


def test_read_job_posting_input_schema_has_url_property():
    schema = next(e for e in TOOL_SCHEMAS if e["name"] == "read_job_posting")["input_schema"]
    assert "url" in schema.get("properties", {})


# ---------------------------------------------------------------------------
# Registry pydantic validation integration
# ---------------------------------------------------------------------------

def test_execute_tool_rejects_bad_url_prefix():
    # Non-allowlisted https:// URLs return SITE_NOT_ALLOWED from the pre-check.
    result = execute_tool("read_job_posting", {"url": "https://jobs.example.com/job_001"})
    assert result["error"] == "SITE_NOT_ALLOWED"


def test_execute_tool_rejects_bad_job_id_in_url():
    # own-site URL with invalid job_id → INVALID_ARGUMENTS from pydantic.
    result = execute_tool("read_job_posting", {"url": own_job_url("job_1")})
    assert result["error"] == "INVALID_ARGUMENTS"


def test_execute_tool_rejects_extra_field_on_read_master_cv():
    result = execute_tool("read_master_cv", {"unexpected": "value"})
    assert result["error"] == "INVALID_ARGUMENTS"


def test_execute_tool_rejects_missing_requirements_in_match_skills():
    result = execute_tool(
        "match_skills",
        {"cv_text": "Python", "job": {"title": "Dev"}},
    )
    assert result["error"] == "INVALID_ARGUMENTS"
    assert "requirements" in result["message"]


def test_execute_tool_rejects_bad_kind_via_pydantic():
    result = execute_tool(
        "save_tailored_cv",
        {"text": "CV", "job_id": "job_001", "kind": "resume"},
    )
    assert result["error"] == "INVALID_ARGUMENTS"


def test_execute_tool_rejects_bad_job_id_via_pydantic():
    result = execute_tool(
        "save_tailored_cv",
        {"text": "CV", "job_id": "job_1", "kind": "cv"},
    )
    assert result["error"] == "INVALID_ARGUMENTS"
    assert "job_id" in result["message"]


def test_execute_tool_validation_error_message_names_bad_field():
    result = execute_tool(
        "submit_application",
        {"cv_path": "a.md", "cover_letter_path": "b.md", "job_id": "bad"},
    )
    assert result["error"] == "INVALID_ARGUMENTS"
    assert "job_id" in result["message"]


def test_execute_tool_still_returns_error_dict_from_tool():
    result = execute_tool(
        "save_tailored_cv",
        {"text": "CV", "job_id": "job_001", "kind": "invalid"},
    )
    assert result["error"] == "INVALID_ARGUMENTS"
