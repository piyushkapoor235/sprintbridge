from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import (
    FutureDatetime,
    InputModel,
    OpportunityStatus,
    OpportunityType,
    PayPeriod,
    SkillList,
    Visibility,
)


class Compensation(BaseModel):
    amount: Decimal
    currency: str
    pay_period: PayPeriod


class OpportunityCreate(InputModel):
    company_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=10000)
    type: OpportunityType
    visibility: Visibility = Visibility.public
    required_skills: SkillList = []
    compensation_amount: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    pay_period: PayPeriod | None = None
    deadline: FutureDatetime

    @model_validator(mode="after")
    def _compensation_all_or_nothing(self):
        present = [self.compensation_amount is not None, self.currency is not None, self.pay_period is not None]
        if any(present) and not all(present):
            raise ValueError("compensation_amount, currency and pay_period must be given together.")
        return self


class OpportunitySummary(BaseModel):
    id: UUID
    company_id: UUID
    company_name: str
    title: str
    type: OpportunityType
    visibility: Visibility
    required_skills: list[str]
    compensation: Compensation | None
    deadline: datetime
    status: OpportunityStatus
    created_at: datetime


class SkillCoverage(BaseModel):
    """Count-based coverage (docs/architecture.md §8). Not a hiring probability."""

    matched_count: int
    required_count: int
    matching_skills: list[str]
    missing_skills: list[str]
    coverage_percent: int | None  # null when the listing has no required skills


class OpportunityDetail(OpportunitySummary):
    description: str
    skill_coverage: SkillCoverage | None  # null for callers without a profile view (e.g. recruiters)
