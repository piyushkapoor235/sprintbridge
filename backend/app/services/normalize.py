"""The single skill/branch normalizer. Mirrors public.normalize_text_array in 0001_core.sql, plus a
small alias map so the same skill always gets one name (e.g. "JS" and "javascript")."""

import re
from urllib.parse import urlparse

# Common spellings -> canonical name. Keep canonical names short and lowercase.
ALIASES = {
    "js": "javascript",
    "es6": "javascript",
    "ecmascript": "javascript",
    "ts": "typescript",
    "reactjs": "react",
    "react.js": "react",
    "react js": "react",
    "nodejs": "node.js",
    "node": "node.js",
    "node js": "node.js",
    "nextjs": "next.js",
    "next js": "next.js",
    "vuejs": "vue",
    "vue.js": "vue",
    "angularjs": "angular",
    "postgres": "postgresql",
    "postgre": "postgresql",
    "psql": "postgresql",
    "mongo": "mongodb",
    "k8s": "kubernetes",
    "golang": "go",
    "py": "python",
    "python3": "python",
    "c sharp": "c#",
    "csharp": "c#",
    "cpp": "c++",
    "ml": "machine learning",
    "dl": "deep learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "amazon web services": "aws",
    "google cloud platform": "gcp",
    "google cloud": "gcp",
    "microsoft azure": "azure",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "power bi": "power bi",
    "powerbi": "power bi",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "tensor flow": "tensorflow",
    "rest api": "rest apis",
    "restful apis": "rest apis",
    "restful api": "rest apis",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "git hub": "github",
}


# "AWS Certified Cloud Practitioner" is evidence of AWS, not a separate skill.
_CERTIFICATION = re.compile(
    r"^(aws|amazon web services|azure|microsoft azure|gcp|google cloud|kubernetes|terraform|oracle|salesforce)\b"
    r".*\b(certified|certification|certificate|practitioner|associate|professional|fundamentals|architect|"
    r"specialty|administrator)\b")


def canonical_skill(value: str) -> str:
    name = re.sub(r"\s+", " ", value.strip().lower())
    certification = _CERTIFICATION.match(name)
    if certification:
        name = certification.group(1)
    return ALIASES.get(name, name)


def normalize_skills(values: list[str]) -> list[str]:
    """Lower-case, trim, apply aliases, drop blanks and duplicates, sort."""
    return sorted({canonical_skill(v) for v in values if v and v.strip()})


def validate_http_url(value: str) -> str:
    """Accept only absolute HTTP(S) URLs without whitespace (docs/architecture.md §4)."""
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or any(c.isspace() for c in value):
        raise ValueError("Must be an http(s) URL.")
    if len(value) > 500:
        raise ValueError("URL is too long.")
    return value


# Category for display and gap grouping. Deterministic (no LLM call), so it is free and consistent.
_CATEGORY_SKILLS = {
    "Languages": "python java javascript typescript c c++ c# go rust kotlin swift php ruby scala r matlab sql bash dart perl",
    "Frameworks & libraries": "react angular vue next.js node.js express django flask fastapi spring spring boot "
                              ".net laravel rails flutter react native tailwind bootstrap jquery redux pandas numpy "
                              "scikit-learn tensorflow pytorch keras spark hadoop",
    "Databases": "postgresql mysql sqlite mongodb redis oracle sql server cassandra dynamodb elasticsearch firebase supabase",
    "Cloud & DevOps": "aws gcp azure docker kubernetes terraform ansible jenkins github actions ci/cd linux nginx "
                      "vercel netlify heroku render airflow dbt kafka",
    "Data & AI": "machine learning deep learning artificial intelligence natural language processing computer vision "
                 "data analysis data visualization statistics power bi tableau excel etl llm",
    "Tools & practices": "git github gitlab jira figma postman rest apis graphql agile scrum testing unit testing "
                         "system design microservices oop dsa data structures algorithms",
    "Professional": "communication english leadership teamwork problem solving project management typing presentation",
}
CATEGORY_OF: dict[str, str] = {}
for _category, _skills in _CATEGORY_SKILLS.items():
    # Multi-word skills are matched first so "spring boot" is not split into "spring" + "boot".
    remaining = f" {_skills} "
    for phrase in ("spring boot", "react native", "github actions", "sql server", "machine learning", "deep learning",
                   "artificial intelligence", "natural language processing", "computer vision", "data analysis",
                   "data visualization", "power bi", "rest apis", "unit testing", "system design", "data structures",
                   "problem solving", "project management"):
        if f" {phrase} " in remaining:
            CATEGORY_OF[phrase] = _category
            remaining = remaining.replace(f" {phrase} ", " ")
    for word in remaining.split():
        CATEGORY_OF.setdefault(word, _category)


def skill_category(skill: str) -> str:
    return CATEGORY_OF.get(canonical_skill(skill), "Other skills")


# Words that are also ordinary English (or single letters) are left to the LLM, which sees context.
_AMBIGUOUS = {"c", "r", "go", "ai", "ml", "dl", "py", "ts", "js", "node", "render", "express", "spring", "spark",
              "excel", "rails", "testing", "communication", "english", "leadership", "teamwork", "presentation",
              "typing", "statistics", "agile", "scrum", "oracle", "swift", "dart", "perl", "ruby", "keras"}
_KNOWN = sorted({s for s in CATEGORY_OF if s not in _AMBIGUOUS} | {a for a in ALIASES if a not in _AMBIGUOUS},
                key=len, reverse=True)
_KNOWN_RE = re.compile(r"(?<![\w+#./-])(" + "|".join(re.escape(s) for s in _KNOWN) + r")(?![\w+#]|\.\w)",
                       re.IGNORECASE)


_SECTIONS = {
    "experience": ["experience", "work experience", "professional experience", "employment", "internships",
                   "internship", "internship experience", "work history"],
    "project": ["projects", "personal projects", "academic projects", "key projects", "project"],
    "education": ["education", "academics", "academic background"],
    "certification": ["certifications", "certificates", "certification", "licenses & certifications", "courses"],
    "skills_list": ["skills", "technical skills", "core skills", "key skills", "tech stack", "technologies", "tools",
                    "summary", "profile", "about", "about me", "objective", "achievements", "interests"],
}
_SECTION_OF = {heading: kind for kind, headings in _SECTIONS.items() for heading in headings}


def _heading(line: str) -> str | None:
    """Section kind if the line is a resume heading like 'EXPERIENCE' or 'Technical Skills:'."""
    key = re.sub(r"[^a-z& ]", "", line.lower()).strip()
    return _SECTION_OF.get(key) if key and len(line) <= 40 else None


_YEAR = re.compile(r"\b(19[5-9]\d|20\d\d)\b")
_BULLET = re.compile(r"^[•\-*\u25aa\u25cf\u2023◦]")
_DATE_ONLY = re.compile(r"(?i)^[\s\d,./()\-–—|]*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?|"
                        r"present|current|now|to|till|[\s\d,./()\-–—|])*$")


def mentioned_skills(text: str) -> list[tuple[str, str, str, int | None]]:
    """(skill, line, context_type, year) for every known skill named verbatim in the text, one per line.
    The context comes from the resume section the line sits under (Experience, Projects, ...); the year is
    the latest year on that line or on the role/project header above it ("May 2026 - Jul 2026").
    A deterministic safety net under the LLM, so the skills and evidence do not vary by run."""
    found: list[tuple[str, str, str, int | None]] = []
    section, header_year, previous = "skills_list", None, []
    for raw in text.splitlines():
        line = raw.strip()
        kind = _heading(line)
        if kind:
            section, header_year, previous = kind, None, []
            continue
        years = [int(y) for y in _YEAR.findall(line)]
        if years and not _BULLET.match(line):
            header_year = max(years)  # a role, project or date line: applies to the bullets under it
            if _DATE_ONLY.match(line) and section != "skills_list":
                for i in previous:  # "Teaching Assistant" above "Aug 2025 - Dec 2025" belongs to that date
                    found[i] = found[i][:3] + (header_year,)
        year = max(years) if years else header_year
        if section == "skills_list":
            year = None  # a skills list says nothing about when the skill was used
        title_like = not years and not _BULLET.match(line) and len(line) <= 70
        previous = []
        seen: set[str] = set()
        for match in _KNOWN_RE.finditer(line):
            skill = canonical_skill(match.group(1))
            if skill not in seen:
                seen.add(skill)
                if title_like:
                    previous.append(len(found))
                found.append((skill, line[:200], section, year))
    return found
