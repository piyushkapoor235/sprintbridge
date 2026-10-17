"""Deterministic fit score (docs/skill-intelligence.md §5.2).

fit = Σ(weight × level_credit × confidence) / Σ(weight)
  weight:       required 2, preferred 1
  level_credit: min(user_level / min_level, 1), 0 when the skill is absent
  confidence:   mentor_verified 1.0, system_assessed 0.8, self_declared 0.3
"""

from dataclasses import dataclass

from app.schemas.common import EvidenceLabel
from app.schemas.skills import FitItem, FitReport

WEIGHT = {"required": 2, "preferred": 1}
CONFIDENCE = {
    EvidenceLabel.mentor_verified: 1.0,
    EvidenceLabel.system_assessed: 0.8,
    EvidenceLabel.self_declared: 0.3,
}


@dataclass(frozen=True)
class Held:
    """The strongest evidence a user has for one skill."""

    label: EvidenceLabel
    level: int | None  # None: mentioned but below level 1


@dataclass(frozen=True)
class Need:
    skill: str
    kind: str  # "required" | "preferred"
    min_level: int
    quote: str | None = None


def strongest(entries: list[Held]) -> Held:
    rank = {EvidenceLabel.mentor_verified: 3, EvidenceLabel.system_assessed: 2, EvidenceLabel.self_declared: 1}
    return max(entries, key=lambda h: (rank[h.label], h.level or 0))


def fit_report(target_type: str, target_id, needs: list[Need], held: dict[str, Held]) -> FitReport:
    items: list[FitItem] = []
    earned = total = 0.0
    required_met = 0
    for need in sorted(needs, key=lambda n: (n.kind != "required", n.skill)):
        weight = WEIGHT[need.kind]
        total += weight
        have = held.get(need.skill)
        level = have.level if have else None
        if have is None or level is None:
            credit = 0.0
            bucket = "missing" if have is None else "under_evidenced"
        else:
            credit = weight * min(level / need.min_level, 1.0) * CONFIDENCE[have.label]
            strong = level >= need.min_level and have.label != EvidenceLabel.self_declared
            bucket = "strong" if strong else "under_evidenced"
        if bucket == "strong" and need.kind == "required":
            required_met += 1
        earned += credit
        items.append(
            FitItem(
                skill=need.skill,
                kind=need.kind,
                min_level=need.min_level,
                user_level=level,
                label=have.label if have else None,
                credit=round(credit, 2),
                bucket=bucket,
                jd_quote=need.quote,
            )
        )
    return FitReport(
        target_type=target_type,
        target_id=target_id,
        fit_percent=round(100 * earned / total) if total else None,
        required_met=required_met,
        required_total=sum(1 for n in needs if n.kind == "required"),
        items=items,
    )
