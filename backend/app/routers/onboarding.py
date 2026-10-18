"""Onboarding: apply for a recruiter / university admin / mentor role; operators approve or reject.
Roles are never self-assigned (docs/threat-model.md): approval happens in the database, audited."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.schemas.onboarding import PendingRoleApplication, RoleApplication, RoleApplicationCreate, RoleDecision

router = APIRouter(tags=["onboarding"])

COLUMNS = ("id, kind, organization_name, job_title, website, niche, experience_summary, status, decision_note, "
           "created_at, reviewed_at")


@router.get("/me/role-applications")
def my_role_applications(actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> list[RoleApplication]:
    return run(db.table("role_applications").select(COLUMNS).eq("user_id", str(actor.user_id))
               .order("created_at", desc=True)).data


@router.post("/me/role-applications", status_code=status.HTTP_201_CREATED)
def apply_for_role(
    body: RoleApplicationCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> RoleApplication:
    return run(db.rpc("submit_role_application", {
        "p_kind": body.kind, "p_organization_name": body.organization_name, "p_job_title": body.job_title,
        "p_website": body.website, "p_niche": body.niche, "p_experience_summary": body.experience_summary,
    })).data


@router.get("/operator/role-applications")
def pending_role_applications(
    actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> list[PendingRoleApplication]:
    return run(db.rpc("operator_role_applications", {})).data


@router.post("/operator/role-applications/{application_id}")
def decide_role_application(
    application_id: UUID, body: RoleDecision, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> RoleApplication:
    return run(db.rpc("review_role_application", {
        "p_id": str(application_id), "p_approve": body.approve, "p_note": body.note,
    })).data
