"""Server-verified memberships and names. Workspace IDs from the client are never trusted."""

from uuid import UUID

from supabase import Client

from app.db import run
from app.errors import ApiError


def my_memberships(db: Client) -> list[dict]:
    """The caller's memberships (RLS returns only their own rows)."""
    return run(db.table("memberships").select("organization_id, role, organizations(name, type)")).data


def is_member(memberships: list[dict], org_id: UUID | str, role: str) -> bool:
    return any(m["organization_id"] == str(org_id) and m["role"] == role for m in memberships)


def require_member(db: Client, org_id: UUID | None, role: str) -> None:
    if org_id is None:
        raise ApiError(422, "VALIDATION_ERROR", "workspace_id is required.", {"workspace_id": "Field required"})
    if not is_member(my_memberships(db), org_id, role):
        raise ApiError(403, "FORBIDDEN", "You are not a member of that workspace.")


def display_names(db: Client, user_ids: set[str]) -> dict[str, str]:
    """Names of people the caller legitimately interacts with (public.display_names)."""
    ids = sorted(i for i in user_ids if i)
    if not ids:
        return {}
    rows = run(db.rpc("display_names", {"p_user_ids": ids})).data or []
    return {r["user_id"]: r["name"] or "Member" for r in rows}
