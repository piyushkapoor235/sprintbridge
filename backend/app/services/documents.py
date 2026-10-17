"""Source text for quote checks: PDF text extraction and a guarded one-shot JD URL fetch."""

import io
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.errors import ApiError

MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_JD_FETCH_BYTES = 2 * 1024 * 1024


def squash(text: str) -> str:
    """Whitespace-insensitive, case-insensitive form used to compare quotes with source text."""
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_in_source(quote: str, source_squashed: str) -> bool:
    q = squash(quote)
    return len(q) >= 2 and q in source_squashed


def pdf_text(raw: bytes) -> str:
    if not raw.startswith(b"%PDF-"):
        raise ApiError(422, "VALIDATION_ERROR", "Upload a PDF file.", {"file": "Not a PDF."})
    try:
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:20])
    except (PdfReadError, ValueError) as exc:
        raise ApiError(422, "VALIDATION_ERROR", "This PDF could not be read.", {"file": "Unreadable PDF."}) from exc
    if len(squash(text)) < 50:
        raise ApiError(422, "VALIDATION_ERROR", "No text found. Scanned/image-only PDFs are not supported.",
                       {"file": "No extractable text."})
    return text


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            return False
    return True


def fetch_job_text(url: str) -> str:
    """Fetch a public job page once, as text. No redirects; private/loopback hosts are refused."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or not _public_host(parsed.hostname):
        raise ApiError(422, "VALIDATION_ERROR", "That URL cannot be fetched; paste the text instead.",
                       {"source_url": "URL not allowed."})
    try:
        with httpx.Client(timeout=10.0, follow_redirects=False) as client:
            with client.stream("GET", url, headers={"User-Agent": "SprintBridge-JD-Fetch/1.0"}) as response:
                if response.status_code != 200:
                    raise ApiError(422, "VALIDATION_ERROR", "Could not fetch that page; paste the text instead.",
                                   {"source_url": f"HTTP {response.status_code}"})
                kind = response.headers.get("content-type", "")
                if not kind.startswith(("text/html", "text/plain")):
                    raise ApiError(422, "VALIDATION_ERROR", "That URL is not a text page; paste the text instead.",
                                   {"source_url": "Unsupported content type."})
                body = b""
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > MAX_JD_FETCH_BYTES:
                        raise ApiError(413, "PAYLOAD_TOO_LARGE", "That page is too large; paste the text instead.")
    except httpx.HTTPError as exc:
        raise ApiError(422, "VALIDATION_ERROR", "Could not fetch that page; paste the text instead.",
                       {"source_url": "Fetch failed."}) from exc

    text = body.decode(response.encoding or "utf-8", errors="replace")
    if kind.startswith("text/html"):
        parser = _TextOnly()
        parser.feed(text)
        text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 50:
        raise ApiError(422, "VALIDATION_ERROR", "No job text found at that URL; paste the text instead.",
                       {"source_url": "No text."})
    return text[:20000]
