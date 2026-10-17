"""Venture Launchpad (stretch, step S18). Acceptance is visible collaboration, not equity or employment."""

import re
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from postgrest import CountMethod
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.errors import ApiError
from app.pagination import Page, PageParams, page_params
from app.schemas.mentors import RequestDecision
from app.schemas.ventures import (
    CollaborationRequest,
    CollaborationRequestCreate,
    CollaborationScope,
    Venture,
    VentureCreate,
)
from app.services.access import display_names

router = APIRouter(tags=["ventures"])

VENTURE_COLUMNS = "id, founder_id, title, problem, industry, stage, needed_skills, created_at"
REQUEST_COLUMNS = "id, venture_id, requester_id, note, status, created_at, updated_at, ventures(title, founder_id)"


def to_ventures(db: Client, rows: list[dict]) -> list[Venture]:
    ids = [r["id"] for r in rows]
    accepted: dict[str, int] = {}
    if ids:
        # Accepted counts are only visible to founders/requesters under RLS; others see 0.
        for r in run(db.table("collaboration_requests").select("venture_id").in_("venture_id", ids).eq("status", "accepted")).data:
            accepted[r["venture_id"]] = accepted.get(r["venture_id"], 0) + 1
    names = display_names(db, {r["founder_id"] for r in rows})
    return [
        Venture(**r, founder_name=names.get(r["founder_id"], "Founder"), accepted_collaborators=accepted.get(r["id"], 0))
        for r in rows
    ]


def to_requests(db: Client, rows: list[dict]) -> list[CollaborationRequest]:
    names = display_names(db, {r["requester_id"] for r in rows})
    return [
        CollaborationRequest(
            **{k: r[k] for k in ("id", "venture_id", "requester_id", "note", "status", "created_at", "updated_at")},
            venture_title=(r.get("ventures") or {}).get("title", "Venture"),
            requester_name=names.get(r["requester_id"], "Member"),
        )
        for r in rows
    ]


def load_venture(db: Client, venture_id: UUID) -> dict:
    rows = run(db.table("ventures").select(VENTURE_COLUMNS).eq("id", str(venture_id)).limit(1)).data
    if not rows:
        raise ApiError(404, "NOT_FOUND", "Venture not found.")
    return rows[0]


@router.get("/ventures")
def list_ventures(
    q: str | None = Query(None, max_length=100),
    skill: str | None = Query(None, max_length=80),
    page: PageParams = Depends(page_params),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> Page[Venture]:
    query = db.table("ventures").select(VENTURE_COLUMNS, count=CountMethod.exact)
    if q and (term := re.sub(r"[%_*,()\\]", " ", q).strip()):
        query = query.ilike("title", f"%{term}%")
    if skill and skill.strip():
        query = query.contains("needed_skills", [skill.strip().lower()])
    result = run(query.order("created_at", desc=True).order("id", desc=True).range(page.offset, page.last_index))
    return Page(items=to_ventures(db, result.data), page=page.page, page_size=page.page_size, total=result.count)


@router.post("/ventures", status_code=status.HTTP_201_CREATED)
def create_venture(body: VentureCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> Venture:
    row = run(db.table("ventures").insert(body.model_dump(mode="json"))).data[0]
    return to_ventures(db, [load_venture(db, row["id"])])[0]


@router.get("/ventures/{venture_id}")
def get_venture(venture_id: UUID, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> Venture:
    return to_ventures(db, [load_venture(db, venture_id)])[0]


@router.post("/ventures/{venture_id}/requests", status_code=status.HTTP_201_CREATED)
def request_collaboration(
    venture_id: UUID, body: CollaborationRequestCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> CollaborationRequest:
    venture = load_venture(db, venture_id)
    if venture["founder_id"] == str(actor.user_id):
        raise ApiError(403, "FORBIDDEN", "You cannot request to join your own venture.")
    row = run(
        db.table("collaboration_requests").insert({"venture_id": str(venture_id), "note": body.note}),
        unique_code="ALREADY_REQUESTED",
    ).data[0]
    return to_requests(db, [{**row, "ventures": {"title": venture["title"], "founder_id": venture["founder_id"]}}])[0]


@router.get("/collaboration-requests")
def list_collaboration_requests(
    scope: CollaborationScope = CollaborationScope.requester,
    page: PageParams = Depends(page_params),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> Page[CollaborationRequest]:
    query = db.table("collaboration_requests").select(REQUEST_COLUMNS, count=CountMethod.exact)
    if scope == CollaborationScope.requester:
        query = query.eq("requester_id", str(actor.user_id))
    else:
        ids = [v["id"] for v in run(db.table("ventures").select("id").eq("founder_id", str(actor.user_id))).data]
        if not ids:
            return Page(items=[], page=page.page, page_size=page.page_size, total=0)
        query = query.in_("venture_id", ids)
    result = run(query.order("created_at", desc=True).order("id", desc=True).range(page.offset, page.last_index))
    return Page(items=to_requests(db, result.data), page=page.page, page_size=page.page_size, total=result.count)


@router.patch("/collaboration-requests/{request_id}")
def decide_collaboration_request(
    request_id: UUID, body: RequestDecision, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> CollaborationRequest:
    rows = run(db.table("collaboration_requests").select(REQUEST_COLUMNS).eq("id", str(request_id)).limit(1)).data
    if not rows:
        raise ApiError(404, "NOT_FOUND", "Request not found.")
    if (rows[0].get("ventures") or {}).get("founder_id") != str(actor.user_id):
        raise ApiError(403, "FORBIDDEN", "Only the founder can accept or decline this request.")
    run(db.table("collaboration_requests").update({"status": body.status.value}).eq("id", str(request_id)))
    rows = run(db.table("collaboration_requests").select(REQUEST_COLUMNS).eq("id", str(request_id)).limit(1)).data
    return to_requests(db, rows)[0]
