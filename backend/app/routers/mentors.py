from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from postgrest import CountMethod
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.errors import ApiError
from app.pagination import Page, PageParams, page_params
from app.schemas.mentors import (
    MentorRequest,
    MentorRequestCreate,
    MentorRequestScope,
    MentorSummary,
    RequestDecision,
)
from app.services.access import display_names

router = APIRouter(tags=["mentors"])

REQUEST_COLUMNS = "id, mentor_id, requester_id, note, status, created_at, updated_at"


def to_requests(db: Client, rows: list[dict]) -> list[MentorRequest]:
    mentor_ids = sorted({r["mentor_id"] for r in rows})
    mentor_users = {
        m["id"]: m["user_id"]
        for m in (run(db.table("mentors").select("id, user_id").in_("id", mentor_ids)).data if mentor_ids else [])
    }
    names = display_names(db, set(mentor_users.values()) | {r["requester_id"] for r in rows})
    return [
        MentorRequest(
            **r,
            mentor_name=names.get(mentor_users.get(r["mentor_id"], ""), "Mentor"),
            requester_name=names.get(r["requester_id"], "Member"),
        )
        for r in rows
    ]


def my_mentor_id(db: Client, actor: Actor) -> str | None:
    rows = run(db.table("mentors").select("id").eq("user_id", str(actor.user_id)).limit(1)).data
    return rows[0]["id"] if rows else None


@router.get("/mentors")
def list_mentors(
    niche: str | None = Query(None, max_length=120),
    skill: str | None = Query(None, max_length=80),
    page: PageParams = Depends(page_params),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> Page[MentorSummary]:
    params = {
        "p_niche": niche.strip() if niche and niche.strip() else None,
        "p_skill": skill.strip() if skill and skill.strip() else None,
        "p_limit": page.page_size,
        "p_offset": page.offset,
    }
    result = run(db.rpc("list_mentors", params)).data
    return Page(items=result["items"], page=page.page, page_size=page.page_size, total=result["total"])


@router.post("/mentor-requests", status_code=status.HTTP_201_CREATED)
def create_mentor_request(
    body: MentorRequestCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> MentorRequest:
    try:
        row = run(
            db.table("mentor_requests").insert({"mentor_id": str(body.mentor_id), "note": body.note}),
            unique_code="ALREADY_REQUESTED",
        ).data[0]
    except ApiError as exc:
        if exc.code == "FORBIDDEN":
            raise ApiError(403, "FORBIDDEN", "You cannot request this mentor.") from exc
        if exc.code == "VALIDATION_ERROR":
            raise ApiError(404, "NOT_FOUND", "Mentor not found.") from exc
        raise
    return to_requests(db, [row])[0]


@router.get("/mentor-requests")
def list_mentor_requests(
    scope: MentorRequestScope = MentorRequestScope.requester,
    page: PageParams = Depends(page_params),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> Page[MentorRequest]:
    query = db.table("mentor_requests").select(REQUEST_COLUMNS, count=CountMethod.exact)
    if scope == MentorRequestScope.requester:
        query = query.eq("requester_id", str(actor.user_id))
    else:
        mentor_id = my_mentor_id(db, actor)
        if mentor_id is None:
            raise ApiError(403, "FORBIDDEN", "You do not have a mentor profile.")
        query = query.eq("mentor_id", mentor_id)
    result = run(query.order("created_at", desc=True).order("id", desc=True).range(page.offset, page.last_index))
    return Page(items=to_requests(db, result.data), page=page.page, page_size=page.page_size, total=result.count)


@router.patch("/mentor-requests/{request_id}")
def decide_mentor_request(
    request_id: UUID, body: RequestDecision, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> MentorRequest:
    rows = run(db.table("mentor_requests").select(REQUEST_COLUMNS).eq("id", str(request_id)).limit(1)).data
    if not rows:
        raise ApiError(404, "NOT_FOUND", "Request not found.")
    if rows[0]["mentor_id"] != my_mentor_id(db, actor):
        raise ApiError(403, "FORBIDDEN", "Only the mentor can accept or decline this request.")
    updated = run(db.table("mentor_requests").update({"status": body.status.value}).eq("id", str(request_id))).data
    return to_requests(db, updated)[0]
