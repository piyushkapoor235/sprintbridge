import re
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from postgrest import CountMethod
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.errors import ApiError
from app.pagination import Page, PageParams, page_params
from app.schemas.applications import Application, ApplicationCreate
from app.schemas.common import OpportunityType, Visibility
from app.schemas.opportunities import OpportunityCreate, OpportunityDetail, OpportunitySummary
from app.schemas.skills import FitReport
from app.services.access import is_member, my_memberships, require_member
from app.services.coverage import skill_coverage
from app.services.fit import Need, fit_report
from app.services.skill_profile import held_map, user_skills

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

COLUMNS = (
    "id, company_id, title, description, type, visibility, required_skills, compensation_amount, "
    "currency, pay_period, deadline, status, created_at, organizations(name)"
)
FIT_SORT_WINDOW = 100  # fit ranking considers the newest visible listings matching the filters


def to_summary(row: dict, model=OpportunitySummary, **extra):
    compensation = None
    if row.get("compensation_amount") is not None:
        compensation = {
            "amount": row["compensation_amount"],
            "currency": row["currency"],
            "pay_period": row["pay_period"],
        }
    return model(
        **{k: row[k] for k in ("id", "company_id", "title", "type", "visibility", "required_skills",
                               "deadline", "status", "created_at")},
        company_name=(row.get("organizations") or {}).get("name", ""),
        compensation=compensation,
        **extra,
    )


def load_opportunity(db: Client, opportunity_id: UUID) -> dict:
    rows = run(db.table("opportunities").select(COLUMNS).eq("id", str(opportunity_id)).limit(1)).data
    if not rows:
        raise ApiError(404, "NOT_FOUND", "Opportunity not found.")
    return rows[0]


def needs_for(db: Client, opportunity: dict) -> list[Need]:
    """Confirmed extracted requirements when present, else the listing's required skills at level 1."""
    extracted = run(
        db.table("job_requirements").select("skill, kind, min_level, quote").eq("opportunity_id", opportunity["id"])
    ).data
    if extracted:
        return [Need(r["skill"], r["kind"], r["min_level"], r.get("quote")) for r in extracted]
    return [Need(skill, "required", 1) for skill in opportunity["required_skills"]]


def detail(db: Client, actor: Actor, row: dict) -> OpportunityDetail:
    coverage = None
    if not is_member(my_memberships(db), row["company_id"], "recruiter"):
        profile = run(db.table("profiles").select("skills").eq("user_id", str(actor.user_id)).limit(1)).data
        coverage = skill_coverage(profile[0]["skills"] if profile else [], row["required_skills"])
    return to_summary(row, OpportunityDetail, description=row["description"], skill_coverage=coverage)


def _search_term(q: str) -> str:
    # Strip characters with meaning in PostgREST filters and LIKE patterns.
    return re.sub(r"[%_*,()\\]", " ", q).strip()


@router.get("")
def list_opportunities(
    q: str | None = Query(None, max_length=100),
    type: OpportunityType | None = None,
    visibility: Visibility | None = None,
    company_id: UUID | None = None,
    sort: str = Query("newest", pattern="^(newest|fit)$"),
    page: PageParams = Depends(page_params),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> Page[OpportunitySummary]:
    query = db.table("opportunities").select(COLUMNS, count=CountMethod.exact)
    if q and (term := _search_term(q)):
        query = query.ilike("title", f"%{term}%")
    if type:
        query = query.eq("type", type.value)
    if visibility:
        query = query.eq("visibility", visibility.value)
    if company_id:
        query = query.eq("company_id", str(company_id))
    query = query.order("created_at", desc=True).order("id", desc=True)

    if sort == "newest":
        result = run(query.range(page.offset, page.last_index))
        return Page(items=[to_summary(r) for r in result.data], page=page.page,
                    page_size=page.page_size, total=result.count)

    # sort=fit: rank the newest window by the deterministic fit score, then paginate.
    result = run(query.range(0, FIT_SORT_WINDOW - 1))
    held = held_map(user_skills(db, str(actor.user_id)))
    scored = [
        (fit_report("opportunity", r["id"], [Need(s, "required", 1) for s in r["required_skills"]], held).fit_percent or 0, r)
        for r in result.data
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)  # stable: newest first among equal fit
    window = scored[page.offset: page.offset + page.page_size]
    return Page(items=[to_summary(r) for _, r in window], page=page.page, page_size=page.page_size,
                total=len(scored))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_opportunity(
    body: OpportunityCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> OpportunityDetail:
    require_member(db, body.company_id, "recruiter")
    created = run(db.table("opportunities").insert(body.model_dump(mode="json"))).data[0]
    return detail(db, actor, load_opportunity(db, created["id"]))


@router.get("/{opportunity_id}")
def get_opportunity(
    opportunity_id: UUID, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> OpportunityDetail:
    return detail(db, actor, load_opportunity(db, opportunity_id))


@router.post("/{opportunity_id}/applications", status_code=status.HTTP_201_CREATED)
def submit_application(
    opportunity_id: UUID, body: ApplicationCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> Application:
    params = {"p_opportunity_id": str(opportunity_id), "p_drive_id": str(body.drive_id) if body.drive_id else None}
    return run(db.rpc("submit_application", params)).data


@router.get("/{opportunity_id}/fit")
def opportunity_fit(
    opportunity_id: UUID, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> FitReport:
    row = load_opportunity(db, opportunity_id)
    held = held_map(user_skills(db, str(actor.user_id)))
    return fit_report("opportunity", row["id"], needs_for(db, row), held)
