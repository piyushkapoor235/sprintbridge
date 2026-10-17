from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import FutureDatetime, InputModel, SkillList


class RosterRow(BaseModel):
    id: UUID
    student_id: str
    name: str
    email: str
    branch: str
    batch: int
    cgpa: Decimal | None
    linked: bool
    label: str = "university_claimed"  # never "verified" (docs/threat-model.md §2)


class RosterRowInput(BaseModel):
    """One parsed CSV row. Header: student_id,name,email,branch,batch,cgpa."""

    student_id: str
    name: str
    email: str
    branch: str
    batch: int
    cgpa: Decimal | None


class RowError(BaseModel):
    row: int  # 1-based data row (header excluded)
    field: str | None
    message: str


class RosterPreview(BaseModel):
    total_rows: int
    valid_rows: list[RosterRowInput]
    errors: list[RowError]


class RosterCommitResult(BaseModel):
    inserted: int
    updated: int
    unchanged: int


class DriveCreate(InputModel):
    university_id: UUID
    opportunity_id: UUID
    allowed_branches: SkillList = []
    batch: int = Field(ge=2000, le=2100)
    min_cgpa: Decimal | None = Field(None, ge=0, le=10, max_digits=4, decimal_places=2)
    required_skills: SkillList = []
    deadline: FutureDatetime


class Drive(BaseModel):
    id: UUID
    university_id: UUID
    university_name: str
    opportunity_id: UUID
    opportunity_title: str
    allowed_branches: list[str]
    batch: int
    min_cgpa: Decimal | None
    required_skills: list[str]
    deadline: datetime
    rules_version: int


class EligibilityReason(BaseModel):
    code: str  # e.g. BRANCH_NOT_ALLOWED, BATCH_MISMATCH, CGPA_BELOW_MINIMUM, CGPA_MISSING,
    #            MISSING_REQUIRED_SKILL, DEADLINE_PASSED, NOT_ON_ROSTER
    message: str


class EligibilityResult(BaseModel):
    drive_id: UUID
    eligible: bool
    reasons: list[EligibilityReason]
    matching_skills: list[str]
    missing_skills: list[str]
    rules_version: int


class UniversityReport(BaseModel):
    university_id: UUID
    branch: str | None
    batch: int | None
    drive_id: UUID | None
    applications: int
    shortlisted: int
    offered: int
    students_with_offers: int  # an offer is not a confirmed placement
