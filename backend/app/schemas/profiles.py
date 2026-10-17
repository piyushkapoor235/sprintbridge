from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import Capability, HttpUrlStr, InputModel, MembershipRole, OrgType, SkillList


class Profile(BaseModel):
    user_id: UUID
    name: str
    specialization: str | None
    education_summary: str | None
    skills: list[str]  # always Self-declared
    portfolio_url: str | None
    is_public: bool
    updated_at: datetime


class Workspace(BaseModel):
    organization_id: UUID
    name: str
    type: OrgType
    role: MembershipRole


class Me(BaseModel):
    user_id: UUID
    email: str | None
    profile: Profile
    capabilities: list[Capability]
    workspaces: list[Workspace]


class ProfilePatch(InputModel):
    """Allowlisted self-editable fields. Anything else is rejected with 422."""

    name: str | None = Field(None, min_length=1, max_length=120)
    specialization: str | None = Field(None, max_length=120)
    education_summary: str | None = Field(None, max_length=1000)
    skills: SkillList | None = None
    portfolio_url: HttpUrlStr | None = None
    is_public: bool | None = None
