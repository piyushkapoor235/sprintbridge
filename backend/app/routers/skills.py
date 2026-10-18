"""Skill intelligence endpoints (docs/skill-intelligence.md). Steps S16-S17, cut-able."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from supabase import Client

from app.auth import Actor, get_actor
from app.db import get_db, run, service_client
from app.errors import ApiError
from app.schemas.skills import (
    FitReport,
    JdCreate,
    JobDescription,
    Recommendation,
    ResumeStatus,
    ResumeUploadResult,
    SkillsResponse,
)
from app.services import llm
from app.services.documents import MAX_RESUME_BYTES, fetch_job_text, pdf_text, quote_in_source, squash
from app.services.fit import Need, fit_report
from app.services.normalize import canonical_skill, mentioned_skills
from app.services.skill_profile import held_map, user_skills

router = APIRouter(tags=["skills"])

JD_COLUMNS = "id, title, source_url, text, created_at, red_flags"


def _skill_name(raw: str) -> str | None:
    name = canonical_skill(raw)
    return name if 0 < len(name) <= 80 else None


# A plain (non-async) endpoint on purpose: FastAPI runs it in a worker thread, so PDF parsing, OCR
# and the LLM call never block the event loop for other users.
@router.post("/me/resume", status_code=status.HTTP_201_CREATED)
def upload_resume(
    file: UploadFile = File(..., description="PDF, max 5 MB"),
    actor: Actor = Depends(get_actor),
    db: Client = Depends(get_db),
) -> ResumeUploadResult:
    raw = file.file.read(MAX_RESUME_BYTES + 1)
    if len(raw) > MAX_RESUME_BYTES:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "The resume must be 5 MB or smaller.")
    sha = hashlib.sha256(raw).hexdigest()
    uid = str(actor.user_id)

    # Same file whose evidence is still current: nothing to re-analyse (saves quota and rate limit).
    # If a newer resume replaced its evidence, analyse it again.
    existing = run(db.table("resumes").select("id, status").eq("sha256", sha).limit(1)).data
    if existing and existing[0]["status"] == "parsed":
        found = run(db.table("skill_evidence").select("skill").eq("resume_id", existing[0]["id"])).data
        if found:
            return ResumeUploadResult(resume_id=existing[0]["id"], status=ResumeStatus.parsed, text_source="cached",
                                      skills_found=len({f["skill"] for f in found}), skills_rejected=0)

    text, text_source = pdf_text(raw)  # the PDF's text layer, or OCR for scanned resumes
    source = squash(text)
    extraction = llm.extract_resume(text)
    run(db.rpc("consume_quota", {"p_metric": "resume_analyses"}))  # counted only after a successful analysis
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
    rows = [
        {"user_id": uid, "resume_id": resume["id"], "skill": name, "source": "resume",
         "context_type": item.context_type, "quote": item.quote[:1000],
         "years": item.years if item.years is not None and 0 <= item.years <= 60 else None,
         "last_used_year": item.last_used_year if item.last_used_year and 1950 <= item.last_used_year <= 2100 else None}
        for name, item in accepted
    ]
    # Deterministic safety net: known skills named in the resume that the model skipped on this run are
    # still recorded, with the context of the section they sit in (no years or recency: those need the model).
    mentions = sorted(mentioned_skills(text), key=lambda m: m[2] == "skills_list")  # in-context lines first
    for name, line, context, year in mentions:
        same = [r for r in rows if r["skill"] == name
                and (squash(r["quote"]) in squash(line) or squash(line) in squash(r["quote"]))]
        for row in same:  # the model's entry for this line; fill in a date it left out
            if row["last_used_year"] is None and row["context_type"] != "skills_list":
                row["last_used_year"] = year
        has_any = any(r["skill"] == name for r in rows)
        if same or (context == "skills_list" and has_any) or not quote_in_source(line, source):
            continue
        rows.append({"user_id": uid, "resume_id": resume["id"], "skill": name, "source": "resume",
                     "context_type": context, "quote": line, "years": None, "last_used_year": year})
    evidence = service_client("skill_evidence")
    run(evidence.table("skill_evidence").delete().eq("user_id", uid).eq("source", "resume"))  # latest resume wins
    if rows:
        run(evidence.table("skill_evidence").insert(rows))
    return ResumeUploadResult(resume_id=resume["id"], status=ResumeStatus.parsed, text_source=text_source,
                              skills_found=len({r["skill"] for r in rows}), skills_rejected=rejected)


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
                          created_at=row["created_at"], requirements=requirements,
                          red_flags=row.get("red_flags") or [])


@router.post("/jds", status_code=status.HTTP_201_CREATED)
def create_jd(body: JdCreate, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)) -> JobDescription:
    text = body.text or fetch_job_text(body.source_url)
    # Identical text pasted before by this user: reuse it (no new analysis, quota or rate-limit use).
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    previous = run(db.table("external_jds").select(JD_COLUMNS).eq("sha256", sha)
                   .order("created_at", desc=True).limit(1)).data
    if previous and _requirements(db, previous[0]["id"]):
        return _to_jd(previous[0], _requirements(db, previous[0]["id"]))

    extraction = llm.extract_job_description(text)  # before saving: an outage leaves nothing half-made
    run(db.rpc("consume_quota", {"p_metric": "jd_reports"}))  # counted only after a successful analysis
    source = squash(text)
    requirements: dict[str, dict] = {}
    for req in extraction.requirements:
        name = _skill_name(req.skill)
        if name and quote_in_source(req.quote, source) and name not in requirements:
            requirements[name] = {"skill": name, "kind": req.kind, "min_level": req.min_level, "quote": req.quote[:1000]}

    row = run(db.table("external_jds").insert({
        "title": body.title or (extraction.title or "")[:200] or None,
        "source_url": body.source_url,
        "text": text,
        "red_flags": [flag[:200] for flag in extraction.red_flags[:10]],
    })).data[0]
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


@router.get("/me/recommendations")
def recommendations(
    limit: int = 6, actor: Actor = Depends(get_actor), db: Client = Depends(get_db)
) -> list[Recommendation]:
    """Open listings the caller can see, ranked by deterministic fit against their skill evidence.
    No LLM call: it reuses the stored evidence, so it is instant and free."""
    uid = str(actor.user_id)
    rows = run(
        db.table("opportunities")
        .select("id, title, type, visibility, required_skills, deadline, organizations(name)")
        .eq("status", "open")
        .gt("deadline", datetime.now(UTC).isoformat())
        .order("created_at", desc=True)
        .limit(100)
    ).data
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    extracted: dict[str, list[Need]] = {}
    for r in run(db.table("job_requirements").select("opportunity_id, skill, kind, min_level, quote")
                 .in_("opportunity_id", ids)).data:
        extracted.setdefault(r["opportunity_id"], []).append(Need(r["skill"], r["kind"], r["min_level"], r.get("quote")))
    applied = {a["opportunity_id"] for a in run(db.table("applications").select("opportunity_id").eq("applicant_id", uid)).data}
    held = held_map(user_skills(db, uid))

    ranked = []
    for row in rows:
        needs = extracted.get(row["id"]) or [Need(skill, "required", 1) for skill in row["required_skills"]]
        if not needs:
            continue
        report = fit_report("opportunity", row["id"], needs, held)
        ranked.append(Recommendation(
            opportunity_id=row["id"], title=row["title"], company_name=(row.get("organizations") or {}).get("name", ""),
            type=row["type"], visibility=row["visibility"], deadline=row["deadline"],
            fit_percent=report.fit_percent, required_met=report.required_met, required_total=report.required_total,
            matching_skills=[i.skill for i in report.items if i.user_level is not None],
            missing_skills=[i.skill for i in report.items if i.bucket == "missing"],
            applied=row["id"] in applied,
        ))
    # Not-yet-applied first, then best fit, then soonest deadline.
    ranked.sort(key=lambda r: (r.applied, -(r.fit_percent or 0), r.deadline))
    return ranked[: max(1, min(limit, 20))]
