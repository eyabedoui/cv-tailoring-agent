
"""
Pydantic v2 input/output schemas for the CV-tailoring tools.

Rules applied:
- extra="forbid" on all models (no undocumented fields accepted).
- Strings are non-empty and length-limited.
- job_id must match ^job_\\d{3}$ for sandbox tools.
- kind is Literal["cv","cover_letter"].
- read_job_posting url must start with ALLOWED_URL_PREFIX + "jobs/" and end
  with a valid job_id pattern.
- job argument for match_skills must have a requirements list.
- find_jobs query is 1–200 chars; site is 1+ chars (allowlist enforced in tool fn).
"""

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent.config import ALLOWED_URL_PREFIX

_JOB_ID_RE = re.compile(r"^job_\d{3}$")
_MAX_TEXT = 20_000
_URL_PREFIX = ALLOWED_URL_PREFIX + "jobs/"


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class ReadJobPostingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: Annotated[str, Field(min_length=1)]

    @field_validator("url")
    @classmethod
    def _url_valid(cls, v: str) -> str:
        if not v.startswith(_URL_PREFIX):
            raise ValueError(
                f"url must start with {_URL_PREFIX!r}, got {v!r}"
            )
        job_id_part = v[len(_URL_PREFIX):]
        if not _JOB_ID_RE.match(job_id_part):
            raise ValueError(
                f"url must end with a job id matching job_NNN, got {job_id_part!r}"
            )
        return v


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
        if not _JOB_ID_RE.match(v):
            raise ValueError(
                f"job_id must match job_NNN, got {v!r}"
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
        if not _JOB_ID_RE.match(v):
            raise ValueError(
                f"job_id must match job_NNN, got {v!r}"
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
