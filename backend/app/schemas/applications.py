from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import ApplicationStatus, InputModel


class ApplicationScope(StrEnum):
    student = "student"
    recruiter = "recruiter"
    university = "university"


class ApplicationCreate(InputModel):
    drive_id: UUID | None = None  # required for campus listings; omitting it never bypasses eligibility


class ProfileSnapshot(BaseModel):
    name: str
    specialization: str | None
    education_summary: str | None
    skills: list[str]
    portfolio_url: str | None


class Application(BaseModel):
    id: UUID
    opportunity_id: UUID
    title: str
    applicant_id: UUID
    drive_id: UUID | None
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    # Only in recruiter and university scopes.
    profile_snapshot: ProfileSnapshot | None = None


class ApplicationStatusPatch(InputModel):
    status: Literal["shortlisted", "offered", "rejected"]
