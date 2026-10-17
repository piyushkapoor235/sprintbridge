"""Plans, usage and simulated payments (docs/business-model.md). Provider is always 'test'."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import InputModel


class Plan(BaseModel):
    code: str
    audience: str
    name: str
    price_inr: int
    period: str  # month | student_year
    limits: dict[str, int]
    features: list[str]


class Usage(BaseModel):
    used: int
    limit: int | None  # null = unlimited


class OrgPlan(BaseModel):
    organization_id: UUID
    name: str
    role: str
    audience: str
    plan: str


class Payment(BaseModel):
    id: UUID
    purpose: str
    amount_inr: int
    status: str
    provider: str
    created_at: datetime


class Payout(BaseModel):
    id: UUID
    source: str
    gross_inr: int
    commission_inr: int
    net_inr: int
    status: str
    release_after: datetime
    created_at: datetime


class Billing(BaseModel):
    seeker_audience: str
    plans: dict[str, str]  # seeker / mentor / founder -> plan code
    organizations: list[OrgPlan]
    usage: dict[str, Usage]
    payments: list[Payment]
    payouts: list[Payout]


class SubscribeRequest(InputModel):
    plan_code: str
    organization_id: UUID | None = None
    confirm_test_payment: bool = False


class SubscribeResult(BaseModel):
    plan_code: str
    audience: str
    organization_id: UUID | None
    amount_inr: int
    payment_id: UUID | None
    renews_at: datetime | None
