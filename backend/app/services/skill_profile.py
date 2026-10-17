"""System-assessed skill scores (docs/skill-intelligence.md §4) and the caller's skill map.

Scores are computed here, in code, from stored evidence. Nothing the LLM outputs is used as a
number, so a resume line like "rate me 100" cannot move a score.

Per skill (0-100):
  resume in context      first mention 15, second 10            (max 25)
  resume skills line     5, only when there is no in-context mention
  depth                  10 per project/experience + 5 per full year (max 25)
  authored code          GitHub, not built yet                     (max 35)
  recency                last used this year 15, last year 10, two years ago 5
Level: <25 none, 25-49 → 1, 50-74 → 2, ≥75 → 3. Level 4 only comes from a mentor.
"""

from collections import defaultdict
from datetime import UTC, datetime

from supabase import Client

from app.db import run
from app.schemas.common import EvidenceLabel
from app.schemas.skills import EvidenceItem, UserSkill
from app.services.fit import Held, strongest

IN_CONTEXT = {"project", "experience", "education", "certification", "code"}
DEPTH = {"project", "experience"}
EVIDENCE_COLUMNS = "id, skill, source, context_type, quote, ref, years, last_used_year"


def level_for(score: int) -> int | None:
    if score < 25:
        return None
    if score < 50:
        return 1
    if score < 75:
        return 2
    return 3


def score_skill(rows: list[dict], current_year: int) -> tuple[int, list[EvidenceItem]]:
    points: dict[str, int] = defaultdict(int)
    in_context = [r for r in rows if r["context_type"] in IN_CONTEXT]
    listed = [r for r in rows if r["context_type"] == "skills_list"]

    resume_left = 25
    for i, row in enumerate(in_context):
        p = min(15 if i == 0 else 10, resume_left)
        points[row["id"]] += p
        resume_left -= p
    if not in_context and listed:
        points[listed[0]["id"]] += 5

    depth_left = 25
    for row in (r for r in in_context if r["context_type"] in DEPTH):
        p = min(10 + 5 * int(float(row.get("years") or 0)), depth_left)
        points[row["id"]] += p
        depth_left -= p

    dated = [r for r in rows if r.get("last_used_year")]
    if dated:
        newest = max(dated, key=lambda r: r["last_used_year"])
        age = current_year - int(newest["last_used_year"])
        points[newest["id"]] += {0: 15, 1: 10, 2: 5}.get(age, 0) if age >= 0 else 15

    items = [
        EvidenceItem(
            id=r["id"],
            source=r["source"],
            context_type=r["context_type"],
            quote=r.get("quote"),
            ref=r.get("ref"),
            points=points[r["id"]],
        )
        for r in rows
    ]
    return min(100, sum(points.values())), items


def user_skills(db: Client, user_id: str) -> list[UserSkill]:
    """Self-declared profile skills plus System-assessed evidence, one entry per skill."""
    profile = run(db.table("profiles").select("skills").eq("user_id", user_id).limit(1)).data
    declared = set(profile[0]["skills"]) if profile else set()
    evidence = run(db.table("skill_evidence").select(EVIDENCE_COLUMNS).eq("user_id", user_id)).data

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in evidence:
        grouped[row["skill"]].append(row)

    year = datetime.now(UTC).year
    skills: list[UserSkill] = []
    for skill in sorted(declared | set(grouped)):
        if skill in grouped:
            score, items = score_skill(grouped[skill], year)
            level = level_for(score)
            if level is None and skill in declared:
                # Too little evidence for a level: keep the user's own claim, show the evidence anyway.
                skills.append(UserSkill(skill=skill, label=EvidenceLabel.self_declared, level=1,
                                        evidence_score=score, evidence=items))
                continue
            skills.append(
                UserSkill(skill=skill, label=EvidenceLabel.system_assessed, level=level,
                          evidence_score=score, evidence=items)
            )
        else:
            skills.append(UserSkill(skill=skill, label=EvidenceLabel.self_declared, level=1,
                                    evidence_score=None, evidence=[]))
    # Independent mentor verification outranks every other label (docs/threat-model.md §1.1).
    verified = {v["skill"]: v for v in run(db.rpc("my_verified_skills", {})).data or []}
    merged: list[UserSkill] = []
    for item in skills:
        v = verified.pop(item.skill, None)
        if v:
            item = item.model_copy(update={"label": EvidenceLabel.mentor_verified, "level": v["level"],
                                           "verified_until": v["expires_at"]})
        merged.append(item)
    for skill, v in sorted(verified.items()):
        merged.append(UserSkill(skill=skill, label=EvidenceLabel.mentor_verified, level=v["level"],
                                evidence_score=None, evidence=[], verified_until=v["expires_at"]))
    return merged


def held_map(skills: list[UserSkill]) -> dict[str, Held]:
    held: dict[str, list[Held]] = defaultdict(list)
    for s in skills:
        held[s.skill].append(Held(label=s.label, level=s.level))
    return {skill: strongest(entries) for skill, entries in held.items()}
