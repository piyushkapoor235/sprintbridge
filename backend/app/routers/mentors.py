from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from postgrest import CountMethod
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.errors import ApiError
from app.pagination import Page, PageParams, page_params
from app.schemas.mentors import (
    DisputeCreate,
    MentorProfilePatch,
    MentorRequest,
    MentorRequestCreate,
    MentorRequestScope,
    MentorSummary,
    RequestDecision,
)
from app.services.access import display_names

router = APIRouter(tags=["mentors"])

REQUEST_COLUMNS = "id, mentor_id, requester_id, note, status, session_status, payment_id, created_at, updated_at"


def to_requests(db: Client, rows: list[dict]) -> list[MentorRequest]:
    mentor_ids = sorted({r["mentor_id"] for r in rows})
    mentor_users = {
        m["id"]: m["user_id"]
        for m in (run(db.table("mentors").select("id, user_id").in_("id", mentor_ids)).data if mentor_ids else [])
    }
    payment_ids = sorted({r["payment_id"] for r in rows if r.get("payment_id")})
    # Payments are readable by their payer; mentors see the price from the request, not the payer's record.
    payments = {
        p["id"]: p
        for p in (run(db.table("payments").select("id, amount_inr, status").in_("id", payment_ids)).data if payment_ids else [])
    }
    names = display_names(db, set(mentor_users.values()) | {r["requester_id"] for r in rows})
    out = []
    for r in rows:
        pay = payments.get(r.get("payment_id"))
        out.append(MentorRequest(
            **{k: r[k] for k in ("id", "mentor_id", "requester_id", "note", "status", "created_at", "updated_at")},
            session_status=r.get("session_status", "pending"),
            price_inr=pay["amount_inr"] if pay else None,
            # Mentors cannot read the requester's payment row. A declined paid request is always refunded
            # (database trigger), so that state is reported without exposing the payment itself.
            payment_status=pay["status"] if pay else (
                None if not r.get("payment_id") else "refunded" if r["status"] == "declined" else "paid"),
            mentor_name=names.get(mentor_users.get(r["mentor_id"], ""), "Mentor"),
            requester_name=names.get(r["requester_id"], "Member"),
        ))
    return out


def my_mentor_id(db: Client, actor: Actor) -> str | None:
    rows = run(db.table("mentors").select("id").eq("user_id", str(actor.user_id)).limit(1)).data
    return rows[0]["id"] if rows else None


def load_request(db: Client, request_id: UUID) -> dict:
    rows = run(db.table("mentor_requests").select(REQUEST_COLUMNS).eq("id", str(request_id)).limit(1)).data
    if not rows:
        raise ApiError(404, "NOT_FOUND", "Request not found.")
    return rows[0]


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


@router.patch("/mentors/me")
def update_my_mentor_profile(
    body: MentorProfilePatch, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> MentorSummary:
    if my_mentor_id(db, actor) is None:
        raise ApiError(403, "FORBIDDEN", "You do not have a mentor profile.")
    changes = body.model_dump(exclude_unset=True)
    if changes:
        run(db.table("mentors").update(changes).eq("user_id", str(actor.user_id)))
    row = run(db.table("mentors").select("id, user_id, niche, experience_summary, session_price_inr, is_active")
              .eq("user_id", str(actor.user_id)).limit(1)).data[0]
    profile = run(db.table("profiles").select("name, skills").eq("user_id", str(actor.user_id)).limit(1)).data[0]
    expertise = run(db.table("mentor_expertise").select("skill, level").eq("mentor_id", row["id"]).order("skill")).data
    return MentorSummary(
        id=row["id"], user_id=row["user_id"], name=profile["name"] or "Mentor", niche=row["niche"],
        experience_summary=row["experience_summary"], skills=profile["skills"], expertise=expertise,
        session_price_inr=row["session_price_inr"], match_reason=None,
    )


@router.post("/mentor-requests", status_code=status.HTTP_201_CREATED)
def create_mentor_request(
    body: MentorRequestCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> MentorRequest:
    # One transaction: quota, test-mode escrow payment for paid mentors, and the request itself.
    created = run(db.rpc("request_mentor", {
        "p_mentor_id": str(body.mentor_id),
        "p_note": body.note,
        "p_confirm_test_payment": body.confirm_test_payment,
    })).data
    return to_requests(db, [load_request(db, created["id"])])[0]


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
    row = load_request(db, request_id)
    if row["mentor_id"] != my_mentor_id(db, actor):
        raise ApiError(403, "FORBIDDEN", "Only the mentor can accept or decline this request.")
    run(db.table("mentor_requests").update({"status": body.status.value}).eq("id", str(request_id)))  # decline refunds
    return to_requests(db, [load_request(db, request_id)])[0]


@router.post("/mentor-requests/{request_id}/complete")
def complete_session(request_id: UUID, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> MentorRequest:
    run(db.rpc("complete_mentor_session", {"p_request_id": str(request_id)}))
    return to_requests(db, [load_request(db, request_id)])[0]


@router.post("/mentor-requests/{request_id}/dispute")
def dispute_session(
    request_id: UUID, body: DisputeCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> MentorRequest:
    run(db.rpc("dispute_mentor_session", {"p_request_id": str(request_id), "p_reason": body.reason}))
    return to_requests(db, [load_request(db, request_id)])[0]
