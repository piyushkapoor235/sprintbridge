"""Independent mentor skill verification (docs/threat-model.md §4)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import InputModel


class VerificationCreate(InputModel):
    skill: str = Field(min_length=1, max_length=80)
    level: int = Field(ge=1, le=4)
    confirm_test_payment: bool = False


class VerifierReveal(BaseModel):
    name: str
    niche: str


class Verification(BaseModel):
    id: UUID
    skill: str
    level_requested: int
    status: str  # assigned | in_session | passed | failed | under_review
    created_at: datetime
    session_started_at: datetime | None
    decided_at: datetime | None
    result_level: int | None
    notes: str | None
    expires_at: datetime | None
    fee_inr: int | None
    retry_after: datetime | None
    verifier: VerifierReveal | None  # revealed only once the session starts


class VerificationCreated(BaseModel):
    id: UUID
    skill: str
    level_requested: int
    status: str
    fee_inr: int


class Assignment(BaseModel):
    id: UUID
    skill: str
    level_requested: int
    status: str
    candidate_name: str
    created_at: datetime
    session_started_at: datetime | None
    decided_at: datetime | None
    result_level: int | None


class AuditTask(BaseModel):
    id: UUID
    skill: str
    level_requested: int
    candidate_name: str
    created_at: datetime
    decided_at: datetime | None


class VerifierQueue(BaseModel):
    expertise: list[dict]
    quality_score: float | None
    assignments: list[Assignment]
    audits: list[AuditTask]


class VerificationResult(InputModel):
    passed: bool
    level: int | None = Field(None, ge=1, le=4)
    notes: str | None = Field(None, max_length=2000)


class AuditResult(InputModel):
    passed: bool
    level: int | None = Field(None, ge=1, le=4)
