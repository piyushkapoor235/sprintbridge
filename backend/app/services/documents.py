"""Source text for quote checks: PDF text extraction and a guarded one-shot JD URL fetch."""

import io
import ipaddress
import re
import socket
import threading
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.errors import ApiError

MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_JD_FETCH_BYTES = 2 * 1024 * 1024


_TYPOGRAPHY = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u2022": " ", "\u25cf": " ", "\u25aa": " ", "\u2023": " ", "\u00b7": " ",
    "\u00a0": " ", "\u200b": "",
    "\ufb01": "fi", "\ufb02": "fl", "\ufb00": "ff", "\ufb03": "ffi", "\ufb04": "ffl",
})


def squash(text: str) -> str:
    """Comparison form for quotes vs source: case-, whitespace- and typography-insensitive
    (curly quotes, dashes, bullets and PDF ligatures are unified), so a faithful quote is not
    rejected over formatting while an invented one still fails."""
    text = text.translate(_TYPOGRAPHY).lower()
    text = re.sub(r"-\s*\n\s*", "-", text)  # hyphenated line breaks in PDFs
    return re.sub(r"\s+", " ", text).strip()


def quote_in_source(quote: str, source_squashed: str) -> bool:
    q = squash(quote)
    return len(q) >= 2 and q in source_squashed


MAX_PAGES = 5  # a resume longer than this is truncated for analysis
MIN_TEXT_CHARS = 120  # below this, treat the PDF as scanned and OCR it


def _text_layer_usable(text: str) -> bool:
    """A real text layer has enough letters and words. Scans have none; broken font encodings
    produce '(cid:123)' runs or symbol soup."""
    if text.count("(cid:") > 5:
        return False
    letters = sum(ch.isalpha() for ch in text)
    words = re.findall(r"[A-Za-z]{3,}", text)
    return letters >= MIN_TEXT_CHARS and len(words) >= 20 and letters / max(1, len(text)) > 0.45


def _column_gutter(lines: list[tuple], page_width: float) -> float | None:
    """x of the vertical gap between two text columns, or None for a single-column page.
    The gutter is the widest strip (between 15% and 85% of the width) that almost no text box
    crosses, with enough lines on each side. Works for sidebars, not just 50/50 splits."""
    bins = 100
    crossing = [0] * bins
    for x0, x1, _, _ in lines:
        for b in range(max(0, int(x0 / page_width * bins)), min(bins, int(x1 / page_width * bins) + 1)):
            crossing[b] += 1
    allowed = max(1, len(lines) // 20)  # a header line or two may span the gutter
    best, run_start = None, None
    for b in range(15, 86):
        if crossing[b] <= allowed:
            run_start = b if run_start is None else run_start
            if best is None or b - run_start > best[1] - best[0]:
                best = (run_start, b)
        else:
            run_start = None
    if best is None:
        return None
    gutter = (best[0] + best[1] + 1) / 2 / bins * page_width
    left = sum(1 for l in lines if l[1] <= gutter)
    right = sum(1 for l in lines if l[0] >= gutter)
    return gutter if left >= 0.2 * len(lines) and right >= 0.2 * len(lines) else None


def _ocr_lines(result, page_width: float) -> list[str]:
    """Order OCR lines for reading. Two-column layouts are read column by column (left, then
    right) instead of interleaving rows from both columns."""
    lines = []
    for box, text in zip(result.boxes, result.txts):
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        lines.append((min(xs), max(xs), min(ys), text))
    if not lines:
        return []
    gutter = _column_gutter(lines, page_width)
    if gutter is None:
        return [l[3] for l in sorted(lines, key=lambda l: (round(l[2] / 12), l[0]))]
    left = [l for l in lines if l[1] <= gutter]
    right = [l for l in lines if l[0] >= gutter]
    spanning = [l for l in lines if l not in left and l not in right]
    row = lambda l: (round(l[2] / 12), l[0])  # same visual row (within ~6px at 2x), then left to right
    top = min(l[2] for l in left + right)
    header = [l for l in spanning if l[2] < top]
    footer = [l for l in spanning if l[2] >= top]
    ordered = sorted(header, key=lambda l: l[2]) + sorted(left, key=row) \
        + sorted(right, key=row) + sorted(footer, key=lambda l: l[2])
    return [l[3] for l in ordered]


_ocr_engine = None
_ocr_lock = threading.Lock()


def _ocr_pdf(raw: bytes) -> str:
    """Render each page and read it with RapidOCR (ONNX, CPU, models bundled with the package)."""
    global _ocr_engine
    import pypdfium2 as pdfium  # imported lazily: only scanned resumes need OCR
    from rapidocr import RapidOCR

    with _ocr_lock:  # one OCR job at a time keeps a small server responsive
        if _ocr_engine is None:
            _ocr_engine = RapidOCR()
        pdf = pdfium.PdfDocument(raw)
        try:
            pages = []
            for index in range(min(len(pdf), MAX_PAGES)):
                page = pdf[index]
                image = page.render(scale=2).to_pil()
                result = _ocr_engine(image)
                if result.txts:
                    pages.append("\n".join(_ocr_lines(result, image.width)))
        finally:
            pdf.close()
    return "\n\n".join(pages)


def pdf_text(raw: bytes) -> tuple[str, str]:
    """Text of a resume PDF and how it was obtained: ("pdf" | "ocr").
    Uses the PDF's own text layer when it is usable, otherwise OCR (scanned or image-only PDFs)."""
    if not raw.startswith(b"%PDF-"):
        raise ApiError(422, "VALIDATION_ERROR", "Upload a PDF file.", {"file": "Not a PDF."})
    try:
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:MAX_PAGES])
    except (PdfReadError, ValueError) as exc:
        raise ApiError(422, "VALIDATION_ERROR", "This PDF could not be read.", {"file": "Unreadable PDF."}) from exc
    if _text_layer_usable(text):
        return text, "pdf"
    try:
        text = _ocr_pdf(raw)
    except Exception as exc:  # noqa: BLE001 - any OCR failure becomes one clear message
        raise ApiError(422, "VALIDATION_ERROR", "We couldn't read this scanned PDF. Try a clearer scan or a text PDF.",
                       {"file": "OCR failed."}) from exc
    if len(squash(text)) < 50:
        raise ApiError(422, "VALIDATION_ERROR", "No readable text found, even with OCR. Try a clearer scan.",
                       {"file": "No extractable text."})
    return text, "ocr"


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
