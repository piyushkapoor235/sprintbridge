"""Role applications: how an account becomes a recruiter, university admin or mentor (migration 0018)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import InputModel
from app.services.normalize import validate_http_url

RoleKind = Literal["recruiter", "university_admin", "mentor"]


class RoleApplicationCreate(InputModel):
    kind: RoleKind
    organization_name: str | None = Field(None, min_length=2, max_length=200)  # company or university
    job_title: str = Field("", max_length=120)
    website: str | None = Field(None, max_length=300)
    niche: str | None = Field(None, min_length=2, max_length=120)  # mentors: area of expertise
    experience_summary: str = Field("", max_length=2000)

    @field_validator("website")
    @classmethod
    def _website(cls, value: str | None) -> str | None:
        return validate_http_url(value) if value else None


class RoleApplication(BaseModel):
    id: UUID
    kind: RoleKind
    organization_name: str | None
    job_title: str
    website: str | None
    niche: str | None
    experience_summary: str
    status: Literal["pending", "approved", "rejected"]
    decision_note: str | None
    created_at: datetime
    reviewed_at: datetime | None


class PendingRoleApplication(BaseModel):
    id: UUID
    kind: RoleKind
    organization_name: str | None
    job_title: str
    website: str | None
    niche: str | None
    experience_summary: str
    created_at: datetime
    applicant_name: str
    applicant_email: str | None
    existing_organization: str | None  # set when approving would join an organization that already exists


class RoleDecision(InputModel):
    approve: bool
    note: str | None = Field(None, max_length=1000)
