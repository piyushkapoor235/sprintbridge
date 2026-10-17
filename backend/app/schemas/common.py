"""Shared wire types. Enum values match the Postgres enums in database/migrations."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.services.normalize import normalize_skills, validate_http_url


class InputModel(BaseModel):
    """Request bodies reject unknown fields, so role/owner/status fields cannot be smuggled in."""

    model_config = ConfigDict(extra="forbid")


class OrgType(StrEnum):
    company = "company"
    university = "university"


class MembershipRole(StrEnum):
    recruiter = "recruiter"
    admin = "admin"


class Capability(StrEnum):
    student = "student"  # every signed-in user
    verified_student = "verified_student"  # linked to a university roster row
    recruiter = "recruiter"
    university_admin = "university_admin"
    mentor = "mentor"
    operator = "operator"


class OpportunityType(StrEnum):
    job = "job"
    internship = "internship"


class Visibility(StrEnum):
    public = "public"
    campus = "campus"


class OpportunityStatus(StrEnum):
    open = "open"
    closed = "closed"


class PayPeriod(StrEnum):
    hour = "hour"
    month = "month"
    year = "year"
    one_time = "one_time"


class ApplicationStatus(StrEnum):
    applied = "applied"
    shortlisted = "shortlisted"
    offered = "offered"
    rejected = "rejected"


class RequestStatus(StrEnum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"


class Decision(StrEnum):
    accepted = "accepted"
    declined = "declined"


class EvidenceLabel(StrEnum):
    """docs/skill-intelligence.md §1. The system never labels its own output 'verified'."""

    self_declared = "self_declared"
    system_assessed = "system_assessed"
    mentor_verified = "mentor_verified"


SkillList = Annotated[list[Annotated[str, Field(max_length=80)]], AfterValidator(normalize_skills), Field(max_length=50)]
HttpUrlStr = Annotated[str, AfterValidator(validate_http_url)]


def _future(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Include a timezone, e.g. 2026-11-15T18:29:59Z.")
    if value <= datetime.now(UTC):
        raise ValueError("Deadline must be in the future.")
    return value


FutureDatetime = Annotated[datetime, AfterValidator(_future)]


class ErrorBody(BaseModel):
    detail: str
    code: str
    field_errors: dict[str, str] = {}
    request_id: str | None = None
