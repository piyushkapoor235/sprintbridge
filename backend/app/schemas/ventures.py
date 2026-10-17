from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import InputModel, RequestStatus, SkillList


class VentureStage(StrEnum):
    idea = "idea"
    prototype = "prototype"
    mvp = "mvp"
    revenue = "revenue"


class CompensationType(StrEnum):
    paid = "paid"
    stipend = "stipend"
    equity = "equity"
    unpaid = "unpaid"
    to_discuss = "to_discuss"


class VentureCreate(InputModel):
    title: str = Field(min_length=1, max_length=200)
    teaser: str = Field(min_length=1, max_length=280)  # public
    problem: str = Field(min_length=1, max_length=4000)  # private: founder + accepted collaborators
    industry: str = Field(min_length=1, max_length=120)
    stage: VentureStage = VentureStage.idea
    needed_skills: SkillList = []
    compensation_type: CompensationType = CompensationType.to_discuss


class Venture(BaseModel):
    id: UUID
    founder_id: UUID
    founder_name: str
    title: str
    teaser: str
    problem: str | None  # null unless the caller is the founder or an accepted collaborator
    industry: str
    stage: VentureStage
    needed_skills: list[str]
    compensation_type: CompensationType
    accepted_collaborators: int
    is_founder: bool
    my_request_status: str | None
    created_at: datetime


class CollaborationScope(StrEnum):
    requester = "requester"
    founder = "founder"


class CollaborationRequestCreate(InputModel):
    note: str = Field(min_length=1, max_length=1000)
    accept_nda: bool  # must be true: details are shared in confidence once accepted


class CollaborationRequest(BaseModel):
    id: UUID
    venture_id: UUID
    venture_title: str
    requester_id: UUID
    requester_name: str
    note: str
    status: RequestStatus
    created_at: datetime
    updated_at: datetime
