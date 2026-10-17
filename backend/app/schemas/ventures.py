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


class VentureCreate(InputModel):
    title: str = Field(min_length=1, max_length=200)
    problem: str = Field(min_length=1, max_length=4000)
    industry: str = Field(min_length=1, max_length=120)
    stage: VentureStage = VentureStage.idea
    needed_skills: SkillList = []


class Venture(BaseModel):
    id: UUID
    founder_id: UUID
    founder_name: str
    title: str
    problem: str
    industry: str
    stage: VentureStage
    needed_skills: list[str]
    accepted_collaborators: int
    created_at: datetime


class CollaborationScope(StrEnum):
    requester = "requester"
    founder = "founder"


class CollaborationRequestCreate(InputModel):
    note: str = Field(min_length=1, max_length=1000)


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
