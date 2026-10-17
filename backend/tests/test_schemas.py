from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.opportunities import OpportunityCreate
from app.schemas.profiles import ProfilePatch
from app.schemas.skills import JdCreate
from app.services.normalize import normalize_skills

BASE = {
    "company_id": "5a0d0000-0000-4000-8000-000000000000",
    "title": "Intern",
    "type": "internship",
    "deadline": "2026-11-15T18:29:59Z",
}


def test_normalize_skills_matches_database_rule():
    assert normalize_skills([" Python", "SQL", "python", "", "  "]) == ["python", "sql"]


def test_profile_patch_normalizes_skills_and_rejects_unknown_fields():
    assert ProfilePatch(skills=["React", "react "]).skills == ["react"]
    with pytest.raises(ValidationError):
        ProfilePatch(role="admin")


@pytest.mark.parametrize("url", ["ftp://x.test", "javascript:alert(1)", "https://bad url.test"])
def test_portfolio_url_must_be_http(url):
    with pytest.raises(ValidationError):
        ProfilePatch(portfolio_url=url)


def test_compensation_is_all_or_nothing():
    OpportunityCreate(**BASE)
    OpportunityCreate(**BASE, compensation_amount=Decimal("25000"), currency="INR", pay_period="month")
    with pytest.raises(ValidationError):
        OpportunityCreate(**BASE, compensation_amount=Decimal("25000"))


def test_jd_needs_text_or_url():
    with pytest.raises(ValidationError):
        JdCreate(title="Only a title")
    assert JdCreate(text="We need Python").text
