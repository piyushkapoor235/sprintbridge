from uuid import UUID

from fastapi import APIRouter, Depends
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.schemas.university import EligibilityResult

router = APIRouter(prefix="/drives", tags=["university"])


@router.get("/{drive_id}/eligibility")
def drive_eligibility(drive_id: UUID, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> EligibilityResult:
    # The same predicate runs inside submit_application, so preview and apply cannot disagree.
    return run(db.rpc("evaluate_drive_eligibility", {"p_drive_id": str(drive_id)})).data
