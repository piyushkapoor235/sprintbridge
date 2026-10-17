"""Plans, usage and simulated (test-mode) payments. No real money moves."""

from fastapi import APIRouter, Depends
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.schemas.billing import Billing, Plan, SubscribeRequest, SubscribeResult

router = APIRouter(tags=["billing"])


@router.get("/plans")
def list_plans(actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> list[Plan]:
    return run(db.table("plans").select("code, audience, name, price_inr, period, limits, features").order("sort")).data


@router.get("/billing")
def my_billing(actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> Billing:
    return run(db.rpc("my_billing", {})).data


@router.post("/subscriptions")
def subscribe(body: SubscribeRequest, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> SubscribeResult:
    return run(db.rpc("subscribe", {
        "p_plan_code": body.plan_code,
        "p_organization_id": str(body.organization_id) if body.organization_id else None,
        "p_confirm_test_payment": body.confirm_test_payment,
    })).data
