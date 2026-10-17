"""Skill intelligence wire types (docs/skill-intelligence.md). Steps S16-S17, cut-able."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import EvidenceLabel, HttpUrlStr, InputModel


class EvidenceItem(BaseModel):
    id: UUID
    source: Literal["resume", "github", "proof", "mentor"]
    context_type: Literal["skills_list", "project", "experience", "education", "certification", "code"]
    quote: str | None
    ref: str | None
    points: int  # this item's contribution to evidence_score


class UserSkill(BaseModel):
    skill: str
    label: EvidenceLabel
    level: int | None = Field(None, ge=1, le=4)  # system-assessed caps at 3; 4 only from a mentor
    evidence_score: int | None = Field(None, ge=0, le=100)  # null for self_declared
    evidence: list[EvidenceItem]
    verified_until: datetime | None = None  # set when an independent mentor verified this skill


class ResumeStatus(StrEnum):
    none = "none"
    uploaded = "uploaded"
    parsed = "parsed"
    failed = "failed"


class SkillsResponse(BaseModel):
    resume_status: ResumeStatus
    items: list[UserSkill]


class ResumeUploadResult(BaseModel):
    resume_id: UUID
    status: ResumeStatus
    skills_found: int
    skills_rejected: int  # extracted but dropped: quote not found in the source text


class JdCreate(InputModel):
    title: str | None = Field(None, max_length=200)
    text: str | None = Field(None, min_length=1, max_length=20000)
    source_url: HttpUrlStr | None = None

    @model_validator(mode="after")
    def _text_or_url(self):
        if not self.text and not self.source_url:
            raise ValueError("Provide the job description text or its URL.")
        return self


class Requirement(BaseModel):
    skill: str
    kind: Literal["required", "preferred"]
    min_level: int = Field(ge=1, le=4)
    quote: str | None


class JobDescription(BaseModel):
    id: UUID
    title: str | None
    source_url: str | None
    created_at: datetime
    requirements: list[Requirement]


class FitItem(BaseModel):
    skill: str
    kind: Literal["required", "preferred"]
    min_level: int
    user_level: int | None
    label: EvidenceLabel | None  # null when missing
    credit: float  # weight x level credit x confidence, already weighted
    bucket: Literal["missing", "under_evidenced", "strong"]
    jd_quote: str | None


class FitReport(BaseModel):
    """Deterministic fit (docs/skill-intelligence.md §5.2). Eligibility is reported separately."""

    target_type: Literal["opportunity", "jd"]
    target_id: UUID
    fit_percent: int | None  # null when the JD has no requirements
    required_met: int
    required_total: int
    items: list[FitItem]
