"""The single skill/branch normalizer. Mirrors public.normalize_text_array in 0001_core.sql."""

from urllib.parse import urlparse


def normalize_skills(values: list[str]) -> list[str]:
    """Lower-case, trim, drop blanks and duplicates, sort."""
    return sorted({v.strip().lower() for v in values if v and v.strip()})


def validate_http_url(value: str) -> str:
    """Accept only absolute HTTP(S) URLs without whitespace (docs/architecture.md §4)."""
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or any(c.isspace() for c in value):
        raise ValueError("Must be an http(s) URL.")
    if len(value) > 500:
        raise ValueError("URL is too long.")
    return value
