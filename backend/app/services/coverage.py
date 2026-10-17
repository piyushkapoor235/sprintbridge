"""Count-based skill coverage (docs/architecture.md §8). Not a hiring probability."""

from app.schemas.opportunities import SkillCoverage
from app.services.normalize import normalize_skills


def skill_coverage(user_skills: list[str], required_skills: list[str]) -> SkillCoverage:
    have = set(normalize_skills(user_skills))
    required = normalize_skills(required_skills)
    matching = [s for s in required if s in have]
    missing = [s for s in required if s not in have]
    n = len(required)
    return SkillCoverage(
        matched_count=len(matching),
        required_count=n,
        matching_skills=matching,
        missing_skills=missing,
        coverage_percent=round(100 * len(matching) / n) if n else None,
    )
