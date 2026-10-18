from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import Response
from postgrest import CountMethod
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.errors import ApiError
from app.pagination import Page, PageParams, page_params
from app.schemas.university import (
    Drive,
    DriveCreate,
    RosterCommitResult,
    RosterPreview,
    RosterRow,
    UniversityReport,
)
from app.services.access import require_member
from app.services.csv_export import to_csv
from app.services.roster_csv import MAX_BYTES, field_errors, parse_roster

router = APIRouter(prefix="/university", tags=["university"])

DRIVE_COLUMNS = (
    "id, university_id, opportunity_id, allowed_branches, batch, min_cgpa, required_skills, deadline, "
    "rules_version, organizations(name), opportunities(title)"
)


def to_drive(row: dict) -> Drive:
    return Drive(
        **{k: row[k] for k in ("id", "university_id", "opportunity_id", "allowed_branches", "batch",
                               "min_cgpa", "required_skills", "deadline", "rules_version")},
        university_name=(row.get("organizations") or {}).get("name", ""),
        opportunity_title=(row.get("opportunities") or {}).get("title") or "Listing",
    )


def _read_csv(file: UploadFile) -> bytes:
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "The CSV must be 1 MB or smaller.")
    return raw


@router.get("/roster")
def list_roster(
    workspace_id: UUID,
    page: PageParams = Depends(page_params),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> Page[RosterRow]:
    require_member(db, workspace_id, "admin")
    result = run(
        db.table("student_roster")
        .select("id, student_id, name, email, branch, batch, cgpa, verified_user_id", count=CountMethod.exact)
        .eq("university_id", str(workspace_id))
        .order("student_id")
        .range(page.offset, page.last_index)
    )
    items = [RosterRow(**{k: v for k, v in r.items() if k != "verified_user_id"}, linked=r["verified_user_id"] is not None)
             for r in result.data]
    return Page(items=items, page=page.page, page_size=page.page_size, total=result.count)


@router.post("/roster/preview")
def preview_roster(
    workspace_id: UUID = Form(...),
    file: UploadFile = File(..., description="CSV, max 1 MB / 100 rows: student_id,name,email,branch,batch,cgpa"),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> RosterPreview:
    require_member(db, workspace_id, "admin")
    return parse_roster(_read_csv(file))  # read-only: nothing is written


@router.post("/roster/commit")
def commit_roster(
    workspace_id: UUID = Form(...),
    file: UploadFile = File(...),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> RosterCommitResult:
    require_member(db, workspace_id, "admin")
    preview = parse_roster(_read_csv(file))  # full revalidation; a preview result is never trusted
    if preview.errors:
        raise ApiError(422, "VALIDATION_ERROR", "Fix the listed rows; nothing was imported.", field_errors(preview))
    rows = [r.model_dump(mode="json") for r in preview.valid_rows]
    return run(db.rpc("commit_roster", {"p_university_id": str(workspace_id), "p_rows": rows})).data


@router.get("/drives")
def list_drives(
    workspace_id: UUID | None = Query(None, description="Admin view of one university; omit for the student view."),
    page: PageParams = Depends(page_params),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> Page[Drive]:
    query = db.table("campus_drives").select(DRIVE_COLUMNS, count=CountMethod.exact)
    if workspace_id:
        require_member(db, workspace_id, "admin")
        query = query.eq("university_id", str(workspace_id))
    else:
        own = run(db.table("student_roster").select("university_id").eq("verified_user_id", str(actor.user_id))).data
        universities = sorted({r["university_id"] for r in own})
        if not universities:
            return Page(items=[], page=page.page, page_size=page.page_size, total=0)
        query = query.in_("university_id", universities)
    result = run(query.order("deadline").order("id").range(page.offset, page.last_index))
    return Page(items=[to_drive(r) for r in result.data], page=page.page, page_size=page.page_size, total=result.count)


@router.post("/drives", status_code=status.HTTP_201_CREATED)
def create_drive(body: DriveCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> Drive:
    require_member(db, body.university_id, "admin")
    created = run(db.table("campus_drives").insert(body.model_dump(mode="json")), unique_code="ALREADY_EXISTS").data[0]
    rows = run(db.table("campus_drives").select(DRIVE_COLUMNS).eq("id", created["id"]).limit(1)).data
    return to_drive(rows[0])


def _report_params(workspace_id: UUID, branch: str | None, batch: int | None, drive_id: UUID | None) -> dict:
    return {
        "p_university_id": str(workspace_id),
        "p_branch": branch,
        "p_batch": batch,
        "p_drive_id": str(drive_id) if drive_id else None,
    }


@router.get("/report")
def report(
    workspace_id: UUID,
    branch: str | None = Query(None, max_length=64),
    batch: int | None = None,
    drive_id: UUID | None = None,
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> UniversityReport:
    return run(db.rpc("university_report", _report_params(workspace_id, branch, batch, drive_id))).data


@router.get(
    "/report.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "Scoped applications CSV."}},
)
def report_csv(
    workspace_id: UUID,
    branch: str | None = Query(None, max_length=64),
    batch: int | None = None,
    drive_id: UUID | None = None,
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> Response:
    rows = run(db.rpc("university_report_rows", _report_params(workspace_id, branch, batch, drive_id))).data
    header = ["student_id", "student_name", "branch", "batch", "opportunity", "company", "status", "applied_at"]
    body = to_csv(header, [
        [r["student_id"], r["student_name"], r["branch"], r["batch"], r["opportunity_title"],
         r["company_name"], r["status"], r["applied_at"]]
        for r in rows
    ])
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="campus-report.csv"'},
    )
