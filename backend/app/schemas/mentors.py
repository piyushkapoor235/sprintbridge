from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import Decision, InputModel, RequestStatus


class Expertise(BaseModel):
    skill: str
    level: int


class MentorSummary(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    niche: str
    experience_summary: str
    skills: list[str]
    mentor_verified: bool = False  # calibrated expert in the filtered skill (ranked first)
    expertise: list[Expertise] = []
    session_price_inr: int | None = None  # null or 0 = free requests; price never affects ranking
    match_reason: str | None  # e.g. "Verified expert in docker"


class MentorRequestScope(StrEnum):
    requester = "requester"
    mentor = "mentor"


class MentorRequestCreate(InputModel):
    mentor_id: UUID
    note: str = Field(min_length=1, max_length=1000)
    confirm_test_payment: bool = False  # required for paid mentors (simulated, no real money)


class MentorProfilePatch(InputModel):
    niche: str | None = Field(None, min_length=1, max_length=120)
    experience_summary: str | None = Field(None, max_length=2000)
    session_price_inr: int | None = Field(None, ge=0, le=100000)
    is_active: bool | None = None


class DisputeCreate(InputModel):
    reason: str = Field(min_length=1, max_length=500)


class MentorRequest(BaseModel):
    id: UUID
    mentor_id: UUID
    mentor_name: str
    requester_id: UUID
    requester_name: str
    note: str
    status: RequestStatus
    session_status: str = "pending"  # pending | completed | disputed
    price_inr: int | None = None
    payment_status: str | None = None  # captured | refunded (test mode)
    created_at: datetime
    updated_at: datetime


class RequestDecision(InputModel):
    status: Decision
