from uuid import UUID

from fastapi import APIRouter, Depends, Query
from postgrest import CountMethod, ReturnMethod
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.errors import ApiError
from app.pagination import Page, PageParams, page_params
from app.schemas.applications import Application, ApplicationScope, ApplicationStatusPatch
from app.services.access import is_member, my_memberships, require_member

router = APIRouter(prefix="/applications", tags=["applications"])

# Explicit columns: eligibility_snapshot has no SELECT grant, so `select=*` would fail by design.
BASE_COLUMNS = "id, opportunity_id, applicant_id, drive_id, status, created_at, updated_at, opportunities(title, company_id)"
ORG_COLUMNS = BASE_COLUMNS + ", profile_snapshot"


def to_application(row: dict, include_snapshot: bool) -> Application:
    opportunity = row.get("opportunities") or {}
    return Application(
        **{k: row[k] for k in ("id", "opportunity_id", "applicant_id", "drive_id", "status", "created_at", "updated_at")},
        title=opportunity.get("title") or "Listing no longer visible",
        profile_snapshot=row.get("profile_snapshot") if include_snapshot else None,
    )


def _empty(page: PageParams) -> Page[Application]:
    return Page(items=[], page=page.page, page_size=page.page_size, total=0)


@router.get("")
def list_applications(
    scope: ApplicationScope = ApplicationScope.student,
    workspace_id: UUID | None = Query(None, description="Required for recruiter and university scopes."),
    opportunity_id: UUID | None = None,
    page: PageParams = Depends(page_params),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> Page[Application]:
    org_view = scope != ApplicationScope.student
    query = db.table("applications").select(ORG_COLUMNS if org_view else BASE_COLUMNS, count=CountMethod.exact)

    if scope == ApplicationScope.student:
        query = query.eq("applicant_id", str(actor.user_id))
    elif scope == ApplicationScope.recruiter:
        require_member(db, workspace_id, "recruiter")
        ids = [r["id"] for r in run(db.table("opportunities").select("id").eq("company_id", str(workspace_id))).data]
        if not ids:
            return _empty(page)
        query = query.in_("opportunity_id", ids)
    else:
        require_member(db, workspace_id, "admin")
        ids = [r["id"] for r in run(db.table("campus_drives").select("id").eq("university_id", str(workspace_id))).data]
        if not ids:
            return _empty(page)
        query = query.in_("drive_id", ids)  # only drive-sourced applications reach university views

    if opportunity_id:
        query = query.eq("opportunity_id", str(opportunity_id))
    result = run(query.order("created_at", desc=True).order("id", desc=True).range(page.offset, page.last_index))
    return Page(
        items=[to_application(r, org_view) for r in result.data],
        page=page.page,
        page_size=page.page_size,
        total=result.count,
    )


@router.patch("/{application_id}")
def update_application_status(
    application_id: UUID, body: ApplicationStatusPatch, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> Application:
    def load() -> dict:
        rows = run(db.table("applications").select(ORG_COLUMNS).eq("id", str(application_id)).limit(1)).data
        if not rows:
            raise ApiError(404, "NOT_FOUND", "Application not found.")
        return rows[0]

    row = load()
    company_id = (row.get("opportunities") or {}).get("company_id")
    if not company_id or not is_member(my_memberships(db), company_id, "recruiter"):
        raise ApiError(403, "FORBIDDEN", "Only the hiring company can change this application's status.")
    # Minimal return: the transition trigger enforces allowed moves (409 INVALID_TRANSITION).
    run(
        db.table("applications")
        .update({"status": body.status}, returning=ReturnMethod.minimal)
        .eq("id", str(application_id))
    )
    return to_application(load(), include_snapshot=True)
