"""Skill intelligence endpoints (docs/skill-intelligence.md). Steps S16-S17, cut-able."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run, service_client
from app.errors import ApiError
from app.schemas.skills import FitReport, JdCreate, JobDescription, ResumeStatus, ResumeUploadResult, SkillsResponse
from app.services import llm
from app.services.documents import MAX_RESUME_BYTES, fetch_job_text, pdf_text, quote_in_source, squash
from app.services.fit import Need, fit_report
from app.services.skill_profile import held_map, user_skills

router = APIRouter(tags=["skills"])

JD_COLUMNS = "id, title, source_url, text, created_at"


def _skill_name(raw: str) -> str | None:
    name = " ".join(raw.strip().lower().split())
    return name if 0 < len(name) <= 80 else None


@router.post("/me/resume", status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(..., description="PDF, max 5 MB"),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> ResumeUploadResult:
    raw = await file.read(MAX_RESUME_BYTES + 1)
    if len(raw) > MAX_RESUME_BYTES:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "The resume must be 5 MB or smaller.")
    source = squash(pdf_text(raw))
    sha = hashlib.sha256(raw).hexdigest()
    uid = str(actor.user_id)

    existing = run(db.table("resumes").select("id, status").eq("sha256", sha).limit(1)).data
    if existing and existing[0]["status"] == "parsed":
        found = run(db.table("skill_evidence").select("id").eq("resume_id", existing[0]["id"])).data
        return ResumeUploadResult(resume_id=existing[0]["id"], status=ResumeStatus.parsed,
                                  skills_found=len(found), skills_rejected=0)  # unchanged file: not re-billed

    extraction = llm.extract_resume(raw)
    accepted, rejected = [], 0
    for item in extraction.skills:
        name = _skill_name(item.skill)
        if name and quote_in_source(item.quote, source):
            accepted.append((name, item))
        else:
            rejected += 1  # quote not literally in the resume: dropped, never scored

    # Server-owned writes (users have no write grant on these tables).
    resumes = service_client("resumes")
    resume = run(resumes.table("resumes").upsert(
        {"user_id": uid, "storage_path": "not_stored", "sha256": sha, "status": "parsed",
         "parsed_at": datetime.now(UTC).isoformat()},
        on_conflict="user_id,sha256",
    )).data[0]
    evidence = service_client("skill_evidence")
    run(evidence.table("skill_evidence").delete().eq("user_id", uid).eq("source", "resume"))  # latest resume wins
    if accepted:
        run(evidence.table("skill_evidence").insert([
            {"user_id": uid, "resume_id": resume["id"], "skill": name, "source": "resume",
             "context_type": item.context_type, "quote": item.quote[:1000],
             "years": item.years if item.years is not None and 0 <= item.years <= 60 else None,
             "last_used_year": item.last_used_year if item.last_used_year and 1950 <= item.last_used_year <= 2100 else None}
            for name, item in accepted
        ]))
    return ResumeUploadResult(resume_id=resume["id"], status=ResumeStatus.parsed,
                              skills_found=len({n for n, _ in accepted}), skills_rejected=rejected)


@router.get("/me/skills")
def my_skills(actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> SkillsResponse:
    latest = run(db.table("resumes").select("status").order("created_at", desc=True).limit(1)).data
    return SkillsResponse(
        resume_status=latest[0]["status"] if latest else ResumeStatus.none,
        items=user_skills(db, str(actor.user_id)),
    )


def _requirements(db: Client, jd_id: str) -> list[dict]:
    return run(db.table("job_requirements").select("skill, kind, min_level, quote").eq("external_jd_id", jd_id)
               .order("kind").order("skill")).data


def _load_jd(db: Client, jd_id: UUID) -> dict:
    rows = run(db.table("external_jds").select(JD_COLUMNS).eq("id", str(jd_id)).limit(1)).data
    if not rows:
        raise ApiError(404, "NOT_FOUND", "Job description not found.")
    return rows[0]


def _to_jd(row: dict, requirements: list[dict]) -> JobDescription:
    return JobDescription(id=row["id"], title=row["title"], source_url=row["source_url"],
                          created_at=row["created_at"], requirements=requirements)


@router.post("/jds", status_code=status.HTTP_201_CREATED)
def create_jd(body: JdCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> JobDescription:
    text = body.text or fetch_job_text(body.source_url)
    extraction = llm.extract_job_description(text)  # before saving: an outage leaves nothing half-made
    source = squash(text)
    requirements: dict[str, dict] = {}
    for req in extraction.requirements:
        name = _skill_name(req.skill)
        if name and quote_in_source(req.quote, source) and name not in requirements:
            requirements[name] = {"skill": name, "kind": req.kind, "min_level": req.min_level, "quote": req.quote[:1000]}

    row = run(db.table("external_jds").insert(
        {"title": body.title or (extraction.title or "")[:200] or None, "source_url": body.source_url, "text": text}
    )).data[0]
    if requirements:
        writer = service_client("job_requirements")
        run(writer.table("job_requirements").insert([{**r, "external_jd_id": row["id"]} for r in requirements.values()]))
    return _to_jd(row, _requirements(db, row["id"]))


@router.get("/jds/{jd_id}")
def get_jd(jd_id: UUID, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> JobDescription:
    row = _load_jd(db, jd_id)
    return _to_jd(row, _requirements(db, row["id"]))


@router.get("/jds/{jd_id}/fit")
def jd_fit(jd_id: UUID, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> FitReport:
    row = _load_jd(db, jd_id)
    needs = [Need(r["skill"], r["kind"], r["min_level"], r.get("quote")) for r in _requirements(db, row["id"])]
    return fit_report("jd", row["id"], needs, held_map(user_skills(db, str(actor.user_id))))
