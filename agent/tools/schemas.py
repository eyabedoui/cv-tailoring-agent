
"""
Pydantic v2 input/output schemas for the CV-tailoring tools.

Rules applied:
- extra="forbid" on all models (no undocumented fields accepted).
- Strings are non-empty and length-limited.
- job_id must pass is_valid_job_id() (accepts job_NNN and site-xxxxxxxx).
- kind is Literal["cv","cover_letter"].
- read_job_posting url must be either an own-site URL with a valid job_id
  or an allowlisted https:// URL.
- job argument for match_skills must have a requirements list.
- find_jobs query is 1–200 chars; site is 1+ chars (allowlist enforced in tool fn).
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MAX_TEXT = 20_000


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class ReadJobPostingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: Annotated[str, Field(min_length=1)]

    @field_validator("url")
    @classmethod
    def _url_valid(cls, v: str) -> str:
        from agent.sites import own_base_url, is_url_allowed
        from agent.job_ids import is_valid_job_id

        # Accept own-site /jobs/<job_id> URLs with a valid job_id.
        own_prefix = own_base_url() + "/jobs/"
        if v.startswith(own_prefix):
            job_id = v[len(own_prefix):]
            if not is_valid_job_id(job_id):
                raise ValueError(
                    f"own-site URL has invalid job_id {job_id!r}"
                )
            return v

        # Accept any URL the allowlist recognises (https:// only).
        if is_url_allowed(v):
            return v

        raise ValueError(
            f"URL must be an own-site /jobs/<id> URL or from an allowed site, got {v!r}"
        )


class ReadMasterCvIn(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MatchSkillsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cv_text: Annotated[str, Field(min_length=1, max_length=_MAX_TEXT)]
    job: dict[str, Any]

    @field_validator("job")
    @classmethod
    def _job_has_requirements(cls, v: dict) -> dict:
        reqs = v.get("requirements")
        if not isinstance(reqs, list):
            raise ValueError(
                "job must contain a 'requirements' key with a list of strings"
            )
        return v


class CheckFormatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cv_text: Annotated[str, Field(min_length=1, max_length=_MAX_TEXT)]


class SaveTailoredCvIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=_MAX_TEXT)]
    job_id: Annotated[str, Field(min_length=1)]
    kind: Literal["cv", "cover_letter"]

    @field_validator("job_id")
    @classmethod
    def _job_id_format(cls, v: str) -> str:
        from agent.job_ids import is_valid_job_id
        if not is_valid_job_id(v):
            raise ValueError(
                f"job_id must match job_NNN or site-xxxxxxxx, got {v!r}"
            )
        return v


class SubmitApplicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cv_path: Annotated[str, Field(min_length=1)]
    cover_letter_path: Annotated[str, Field(min_length=1)]
    job_id: Annotated[str, Field(min_length=1)]

    @field_validator("job_id")
    @classmethod
    def _job_id_format(cls, v: str) -> str:
        from agent.job_ids import is_valid_job_id
        if not is_valid_job_id(v):
            raise ValueError(
                f"job_id must match job_NNN or site-xxxxxxxx, got {v!r}"
            )
        return v


# ---------------------------------------------------------------------------
# find_jobs — input
# ---------------------------------------------------------------------------

class FindJobsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, Field(min_length=1, max_length=200)]
    site: Annotated[str, Field(min_length=1)]


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class ReadJobPostingOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    title: str
    company: str
    requirements: list[str]
    text: str


class ReadMasterCvOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    sections: dict[str, Any]


class MatchSkillsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matched: list[str]
    missing: list[str]
    score: float


class CheckFormatOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    issues: list[str]


class SaveTailoredCvOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    saved: bool


class SubmitApplicationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    application_id: str


class FindJobsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jobs: list[dict[str, Any]]
    site: str
    count: int
    truncated: bool


# ---------------------------------------------------------------------------
# Registry: name -> (InputModel, OutputModel)
# ---------------------------------------------------------------------------

TOOL_SCHEMA_MAP: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    "read_job_posting":  (ReadJobPostingIn,  ReadJobPostingOut),
    "read_master_cv":    (ReadMasterCvIn,    ReadMasterCvOut),
    "match_skills":      (MatchSkillsIn,     MatchSkillsOut),
    "check_format":      (CheckFormatIn,     CheckFormatOut),
    "save_tailored_cv":  (SaveTailoredCvIn,  SaveTailoredCvOut),
    "submit_application":(SubmitApplicationIn, SubmitApplicationOut),
    "find_jobs":         (FindJobsIn,         FindJobsOut),
}
