"""Pure services: coverage, fit formula, skill scoring, roster CSV, CSV export, DB error mapping."""

import pytest
from postgrest.exceptions import APIError

from app.db import translate
from app.errors import ApiError
from app.schemas.common import EvidenceLabel
from app.services.coverage import skill_coverage
from app.services.csv_export import safe_cell, to_csv
from app.services.documents import quote_in_source, squash
from app.services.fit import Held, Need, fit_report
from app.services.normalize import canonical_skill, mentioned_skills, skill_category
from app.services.roster_csv import parse_roster
from app.services.skill_profile import level_for, score_skill

# --- coverage (architecture.md §8) ---------------------------------------------------


@pytest.mark.parametrize(
    ("have", "need", "percent", "missing"),
    [
        (["Python", "SQL"], ["python", "sql", "docker"], 67, ["docker"]),
        ([], ["python"], 0, ["python"]),
        (["python"], ["Python", "python "], 100, []),
        (["python"], [], None, []),
    ],
)
def test_coverage(have, need, percent, missing):
    result = skill_coverage(have, need)
    assert result.coverage_percent == percent and result.missing_skills == missing


# --- fit (skill-intelligence.md §5.2 worked example) -----------------------------------


def test_fit_worked_example_is_56_percent():
    needs = [Need("python", "required", 2), Need("sql", "required", 2), Need("docker", "required", 2),
             Need("react", "preferred", 1)]
    held = {
        "python": Held(EvidenceLabel.system_assessed, 2),
        "sql": Held(EvidenceLabel.mentor_verified, 3),
        "react": Held(EvidenceLabel.self_declared, 1),
    }
    report = fit_report("opportunity", "00000000-0000-4000-8000-000000000000", needs, held)
    assert report.fit_percent == 56
    assert (report.required_met, report.required_total) == (2, 3)
    buckets = {i.skill: (i.bucket, i.credit) for i in report.items}
    assert buckets == {"python": ("strong", 1.6), "sql": ("strong", 2.0), "docker": ("missing", 0.0),
                       "react": ("under_evidenced", 0.3)}


def test_fit_without_requirements_is_null():
    assert fit_report("jd", "00000000-0000-4000-8000-000000000000", [], {}).fit_percent is None


# --- skill scoring (skill-intelligence.md §4) ------------------------------------------


def _ev(i, context, years=None, year=None):
    return {"id": f"00000000-0000-4000-8000-00000000000{i}", "source": "resume", "context_type": context,
            "quote": "q", "ref": None, "years": years, "last_used_year": year}


def test_score_in_context_project_with_recency():
    score, items = score_skill([_ev(1, "project", years=0.5, year=2026)], current_year=2026)
    assert score == 20 + 10 + 25  # in-context + one project + used this year
    assert level_for(score) == 2 and items[0].points == score


def test_internship_experience_reaches_working_level():
    score, _ = score_skill([_ev(1, "experience", year=2026), _ev(2, "skills_list")], current_year=2026)
    assert score == 20 + 15 + 25 and level_for(score) == 2


def test_keyword_stuffing_is_capped():
    stuffed = [_ev(i, "skills_list") for i in range(1, 6)]
    score, _ = score_skill(stuffed, current_year=2026)
    assert score == 5 and level_for(score) is None


def test_score_caps_and_level_bands():
    rows = [_ev(1, "experience", years=3, year=2026), _ev(2, "project", years=1), _ev(3, "project")]
    score, _ = score_skill(rows, current_year=2026)
    assert score == 35 + 40 + 25  # context cap 35, depth cap 40, recency 25
    assert level_for(score) == 3
    assert [level_for(s) for s in (24, 25, 50, 75, 100)] == [None, 1, 2, 3, 3]


# --- quote check -----------------------------------------------------------------------


def test_quote_check_is_whitespace_and_case_insensitive():
    source = squash("Built ETL\n pipelines in  Python and SQL")
    assert quote_in_source("built etl pipelines in python", source)
    assert not quote_in_source("Expert in Kubernetes", source)


# --- roster CSV ------------------------------------------------------------------------

HEADER = b"student_id,name,email,branch,batch,cgpa\n"


def test_roster_valid_rows_are_normalized():
    preview = parse_roster(HEADER + b"S1,Asha,Asha@Uni.test, CSE ,2027,8.1\nS2,Vikram,v@uni.test,IT,2027,\n")
    assert preview.errors == [] and preview.total_rows == 2
    assert (preview.valid_rows[0].email, preview.valid_rows[0].branch, str(preview.valid_rows[0].cgpa)) == ("asha@uni.test", "cse", "8.10")
    assert preview.valid_rows[1].cgpa is None


def test_roster_errors_are_per_row_and_field():
    preview = parse_roster(HEADER + b"S1,A,a@u.test,CSE,2027,11\nS1,B,bad-email,CSE,27,7.5\nS3,C,c@u.test,CSE,2027,7.555\n")
    found = {(e.row, e.field) for e in preview.errors}
    assert found == {(1, "cgpa"), (2, "student_id"), (2, "email"), (2, "batch"), (3, "cgpa")}
    assert preview.valid_rows == []


def test_roster_header_and_size_limits():
    with pytest.raises(ApiError) as caught:
        parse_roster(b"id,name\n1,a\n")
    assert caught.value.status_code == 422
    with pytest.raises(ApiError) as caught:
        parse_roster(HEADER + b"".join(f"S{i},N,n{i}@u.test,cse,2027,8\n".encode() for i in range(101)))
    assert caught.value.status_code == 413


def test_fixture_csv_is_valid():
    from pathlib import Path

    raw = (Path(__file__).resolve().parents[2] / "database" / "fixtures" / "students.csv").read_bytes()
    assert parse_roster(raw).errors == []


# --- CSV export ------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["=SUM(A1)", "+1", "-1", "@cmd", "\tx"])
def test_formula_cells_are_neutralized(value):
    assert safe_cell(value).startswith("'")


def test_csv_round_trip_plain_values():
    assert to_csv(["a", "b"], [["x", None]]) == "a,b\r\nx,\r\n"


# --- database error mapping (api-contract.md §4) ---------------------------------------


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        ({"code": "PT409", "hint": "ALREADY_APPLIED", "message": "dup"}, 409, "ALREADY_APPLIED"),
        ({"code": "PT403", "hint": "NOT_ELIGIBLE", "message": "no"}, 403, "NOT_ELIGIBLE"),
        ({"code": "23505", "message": "duplicate key value violates unique constraint"}, 409, "ALREADY_REQUESTED"),
        ({"code": "42501", "message": "new row violates row-level security policy for table x"}, 403, "FORBIDDEN"),
        ({"code": "23514", "message": "check"}, 422, "VALIDATION_ERROR"),
        ({"code": "PGRST999", "message": "weird"}, 500, "INTERNAL_ERROR"),
    ],
)
def test_translate(error, status, code):
    result = translate(APIError(error), unique_code="ALREADY_REQUESTED")
    assert (result.status_code, result.code) == (status, code)
    assert "table" not in result.detail and "constraint" not in result.detail


RESUME = """Asha Rao
TECHNICAL SKILLS
Languages: Java, Python (2024)
EXPERIENCE
Backend Intern, Globex · May 2025 - Jul 2026
• Set up a GitHub Actions pipeline; tuned Postgres queries
Teaching Assistant, Data Structures
Aug 2023 - Dec 2023
• Java labs
Projects
Game engine (2024)
• Node.js and C++ game engine
"""


def test_mentioned_skills_uses_resume_sections_and_dates():
    found = {(skill, context, year) for skill, _, context, year in mentioned_skills(RESUME)}
    assert {("java", "skills_list", None), ("python", "skills_list", None),
            ("github actions", "experience", 2026), ("postgresql", "experience", 2026),
            ("data structures", "experience", 2023), ("java", "experience", 2023),
            ("node.js", "project", 2024), ("c++", "project", 2024)} == found
    assert "github" not in {skill for skill, *_ in found}  # the longer phrase wins


def test_certifications_count_as_the_vendor_skill():
    assert canonical_skill("AWS Certified Cloud Practitioner") == "aws"
    assert canonical_skill("Microsoft Azure Fundamentals") == "azure"
    assert canonical_skill("aws lambda") == "aws lambda"


def test_mentioned_skills_skips_ordinary_words():
    assert mentioned_skills("I go to the gym and excel at it. Email a.js@x.test. Spring 2026.") == []


def test_skill_categories():
    assert skill_category("Spring Boot") == "Frameworks & libraries"
    assert skill_category("postgres") == "Databases"
    assert skill_category("GitHub Actions") == "Cloud & DevOps"
    assert skill_category("basket weaving") == "Other skills"
