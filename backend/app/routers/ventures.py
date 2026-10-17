"""Venture Launchpad: founders post a public teaser; full details only for accepted collaborators."""

import re
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from postgrest import CountMethod, ReturnMethod
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

# `problem` is not selectable (column grant); it comes from venture_private_details() when allowed.
VENTURE_COLUMNS = "id, founder_id, title, teaser, industry, stage, needed_skills, compensation_type, created_at"
REQUEST_COLUMNS = "id, venture_id, requester_id, note, status, created_at, updated_at, ventures(title, founder_id)"


def to_ventures(db: Client, actor: Actor, rows: list[dict], with_details: bool = False) -> list[Venture]:
    ids = [r["id"] for r in rows]
    accepted: dict[str, int] = {}
    mine: dict[str, str] = {}
    if ids:
        visible = run(db.table("collaboration_requests").select("venture_id, requester_id, status").in_("venture_id", ids)).data
        for r in visible:
            if r["status"] == "accepted":
                accepted[r["venture_id"]] = accepted.get(r["venture_id"], 0) + 1
            if r["requester_id"] == str(actor.user_id):
                mine[r["venture_id"]] = r["status"]
    names = display_names(db, {r["founder_id"] for r in rows})
    out = []
    for r in rows:
        problem = run(db.rpc("venture_private_details", {"p_venture_id": r["id"]})).data if with_details else None
        out.append(Venture(
            **r,
            problem=problem,
            founder_name=names.get(r["founder_id"], "Founder"),
            accepted_collaborators=accepted.get(r["id"], 0),
            is_founder=r["founder_id"] == str(actor.user_id),
            my_request_status=mine.get(r["id"]),
        ))
    return out


def load_venture(db: Client, venture_id: UUID) -> dict:
    rows = run(db.table("ventures").select(VENTURE_COLUMNS).eq("id", str(venture_id)).limit(1)).data
    if not rows:
        raise ApiError(404, "NOT_FOUND", "Venture not found.")
    return rows[0]


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


@router.get("/ventures")
def list_ventures(
    q: str | None = Query(None, max_length=100),
    skill: str | None = Query(None, max_length=80),
    mine: bool = False,
    page: PageParams = Depends(page_params),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> Page[Venture]:
    query = db.table("ventures").select(VENTURE_COLUMNS, count=CountMethod.exact)
    if q and (term := re.sub(r"[%_*,()\\]", " ", q).strip()):
        query = query.ilike("title", f"%{term}%")
    if skill and skill.strip():
        query = query.contains("needed_skills", [skill.strip().lower()])
    if mine:
        query = query.eq("founder_id", str(actor.user_id))
    result = run(query.order("created_at", desc=True).order("id", desc=True).range(page.offset, page.last_index))
    return Page(items=to_ventures(db, actor, result.data), page=page.page, page_size=page.page_size, total=result.count)


@router.post("/ventures", status_code=status.HTTP_201_CREATED)
def create_venture(body: VentureCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> Venture:
    # Minimal return: the inserted row includes `problem`, which is not directly selectable.
    run(db.table("ventures").insert(body.model_dump(mode="json"), returning=ReturnMethod.minimal))
    created = run(db.table("ventures").select(VENTURE_COLUMNS).eq("founder_id", str(actor.user_id))
                  .eq("title", body.title).order("created_at", desc=True).limit(1)).data[0]
    return to_ventures(db, actor, [created], with_details=True)[0]


@router.get("/ventures/{venture_id}")
def get_venture(venture_id: UUID, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> Venture:
    return to_ventures(db, actor, [load_venture(db, venture_id)], with_details=True)[0]


@router.post("/ventures/{venture_id}/requests", status_code=status.HTTP_201_CREATED)
def request_collaboration(
    venture_id: UUID, body: CollaborationRequestCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> CollaborationRequest:
    venture = load_venture(db, venture_id)
    if venture["founder_id"] == str(actor.user_id):
        raise ApiError(403, "FORBIDDEN", "You cannot request to join your own venture.")
    if not body.accept_nda:
        raise ApiError(422, "VALIDATION_ERROR", "Accept the confidentiality terms to send a request.",
                       {"accept_nda": "Required"})
    row = run(
        db.table("collaboration_requests").insert(
            {"venture_id": str(venture_id), "note": body.note, "nda_accepted": True}),
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
