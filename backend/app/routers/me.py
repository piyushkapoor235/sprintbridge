from fastapi import APIRouter, Depends
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run
from app.errors import ApiError
from app.schemas.common import Capability
from app.schemas.profiles import Me, ProfilePatch
from app.services.access import my_memberships

router = APIRouter(tags=["me"])

PROFILE_COLUMNS = "user_id, name, specialization, education_summary, skills, portfolio_url, is_public, updated_at"


def build_me(db: Client, actor: Actor) -> Me:
    uid = str(actor.user_id)
    profiles = run(db.table("profiles").select(PROFILE_COLUMNS).eq("user_id", uid).limit(1)).data
    if not profiles:
        raise ApiError(404, "NOT_FOUND", "Profile not found.")
    memberships = my_memberships(db)
    grants = {g["role"] for g in run(db.table("role_grants").select("role")).data}
    on_roster = run(db.table("student_roster").select("id").eq("verified_user_id", uid).limit(1)).data

    capabilities = [Capability.student]
    if on_roster:
        capabilities.append(Capability.verified_student)
    if any(m["role"] == "recruiter" for m in memberships):
        capabilities.append(Capability.recruiter)
    if any(m["role"] == "admin" for m in memberships):
        capabilities.append(Capability.university_admin)
    capabilities += [Capability(g) for g in ("mentor", "operator") if g in grants]

    workspaces = [
        {
            "organization_id": m["organization_id"],
            "name": m["organizations"]["name"],
            "type": m["organizations"]["type"],
            "role": m["role"],
        }
        for m in sorted(memberships, key=lambda m: (m["organizations"]["name"], m["role"]))
    ]
    return Me(
        user_id=actor.user_id,
        email=actor.email,
        profile=profiles[0],
        capabilities=capabilities,
        workspaces=workspaces,
    )


@router.get("/me")
def get_me(actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> Me:
    return build_me(db, actor)


@router.patch("/me")
def patch_me(body: ProfilePatch, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> Me:
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise ApiError(422, "VALIDATION_ERROR", "Some fields are invalid.", {"name": "Name cannot be empty."})
    if changes:
        run(db.table("profiles").update(changes).eq("user_id", str(actor.user_id)))
    return build_me(db, actor)
