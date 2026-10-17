"""Reports and operator moderation (docs/threat-model.md §5, §11)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import InputModel


class ReportCreate(InputModel):
    target_type: Literal["opportunity", "venture"]
    target_id: UUID
    reason: Literal["scam", "fake", "abusive", "misleading", "other"]
    details: str | None = Field(None, max_length=1000)


class ReportCreated(BaseModel):
    id: UUID
    status: str


class ModerationAction(InputModel):
    target_type: Literal["opportunity", "venture"]
    target_id: UUID
    action: Literal["dismiss", "hide", "remove", "restore"]
    note: str | None = Field(None, max_length=500)


class PayoutAction(InputModel):
    action: Literal["release", "refund"]


class OperatorQueue(BaseModel):
    reports: list[dict]
    flagged: list[dict]
    payouts: list[dict]
    audit: list[dict]
