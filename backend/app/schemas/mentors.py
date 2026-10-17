from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import Decision, InputModel, RequestStatus


class MentorSummary(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    niche: str
    experience_summary: str
    skills: list[str]
    mentor_verified: bool = False  # becomes meaningful once mentor verification exists
    match_reason: str | None  # e.g. "Matches skill: docker" when filtered by skill


class MentorRequestScope(StrEnum):
    requester = "requester"
    mentor = "mentor"


class MentorRequestCreate(InputModel):
    mentor_id: UUID
    note: str = Field(min_length=1, max_length=1000)


class MentorRequest(BaseModel):
    id: UUID
    mentor_id: UUID
    mentor_name: str
    requester_id: UUID
    requester_name: str
    note: str
    status: RequestStatus
    created_at: datetime
    updated_at: datetime


class RequestDecision(InputModel):
    status: Decision
