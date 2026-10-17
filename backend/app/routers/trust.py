"""Reports and operator moderation, payouts and audit log (docs/threat-model.md §5, §9, §11)."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.schemas.trust import ModerationAction, OperatorQueue, PayoutAction, ReportCreate, ReportCreated

router = APIRouter(tags=["trust"])


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def report(body: ReportCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> ReportCreated:
    row = run(db.table("content_reports").insert(body.model_dump(mode="json")), unique_code="ALREADY_REPORTED").data[0]
    return ReportCreated(id=row["id"], status=row["status"])


@router.get("/operator/queue")
def operator_queue(actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> OperatorQueue:
    return run(db.rpc("operator_queue", {})).data


@router.post("/operator/moderate")
def moderate(body: ModerationAction, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> dict:
    return run(db.rpc("operator_moderate", {
        "p_target_type": body.target_type, "p_target_id": str(body.target_id),
        "p_action": body.action, "p_note": body.note,
    })).data


@router.post("/operator/payouts/release-due")
def release_due(actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> dict:
    return {"released": run(db.rpc("operator_release_due_payouts", {})).data}


@router.post("/operator/payouts/{payout_id}")
def resolve_payout(
    payout_id: UUID, body: PayoutAction, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> dict:
    return run(db.rpc("operator_resolve_payout", {"p_payout_id": str(payout_id), "p_action": body.action})).data
