"""Independent mentor skill verification: candidates request, the system assigns, mentors verify."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.schemas.verification import (
    AuditResult,
    Verification,
    VerificationCreate,
    VerificationCreated,
    VerificationResult,
    VerifierQueue,
)

router = APIRouter(tags=["verification"])


@router.post("/verifications", status_code=status.HTTP_201_CREATED)
def request_verification(
    body: VerificationCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> VerificationCreated:
    return run(db.rpc("request_skill_verification", {
        "p_skill": body.skill, "p_level": body.level, "p_confirm_test_payment": body.confirm_test_payment,
    })).data


@router.get("/verifications")
def my_verifications(actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> list[Verification]:
    return run(db.rpc("my_verifications", {})).data


@router.get("/verifications/queue")
def verifier_queue(actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> VerifierQueue:
    return run(db.rpc("verifier_queue", {})).data


@router.post("/verifications/{verification_id}/start")
def start_session(verification_id: UUID, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> dict:
    return run(db.rpc("start_verification_session", {"p_request_id": str(verification_id)})).data


@router.post("/verifications/{verification_id}/result")
def submit_result(
    verification_id: UUID, body: VerificationResult, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> dict:
    return run(db.rpc("submit_verification_result", {
        "p_request_id": str(verification_id), "p_passed": body.passed,
        "p_level": body.level, "p_notes": body.notes or "",
    })).data


@router.post("/verification-audits/{audit_id}")
def submit_audit(
    audit_id: UUID, body: AuditResult, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> dict:
    return run(db.rpc("submit_verification_audit", {
        "p_audit_id": str(audit_id), "p_passed": body.passed, "p_level": body.level,
    })).data
