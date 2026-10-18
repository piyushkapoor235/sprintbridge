"""Resume text extraction: text-layer detection, OCR reading order, scanned PDFs. No network."""

import io
from types import SimpleNamespace

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.errors import ApiError
from app.services import documents

BODY = [
    "Vikram Shah - Backend Developer",
    "Built REST APIs in Java with Spring Boot serving twenty thousand requests per day.",
    "Wrote SQL migrations and tuned PostgreSQL queries, cutting report time by forty percent.",
    "Containerised two services with Docker for the staging environment.",
    "Python ETL job that cleans placement exports nightly and loads them into SQLite.",
]


def text_pdf(lines=BODY) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


def scanned_pdf(lines=BODY) -> bytes:
    """The same page as an image only (no text layer), like a phone or office scan."""
    import pypdfium2 as pdfium

    image = pdfium.PdfDocument(text_pdf(lines))[0].render(scale=2).to_pil().convert("L")
    buf = io.BytesIO()
    image.save(buf, "PDF", resolution=144)
    return buf.getvalue()


def ocr_result(lines):
    """A RapidOCR-shaped result from (x0, x1, y, text) tuples."""
    return SimpleNamespace(
        boxes=[[(x0, y), (x1, y), (x1, y + 10), (x0, y + 10)] for x0, x1, y, _ in lines],
        txts=[t for *_, t in lines],
    )


def test_text_layer_detection():
    assert documents._text_layer_usable(" ".join(BODY))
    assert not documents._text_layer_usable("")
    assert not documents._text_layer_usable("(cid:12)" * 50 + " ".join(BODY))  # broken font encoding
    assert not documents._text_layer_usable("@#$% 1234 ~~~ " * 40)  # symbol soup


def test_text_pdf_uses_its_text_layer(monkeypatch):
    monkeypatch.setattr(documents, "_ocr_pdf", lambda raw: pytest.fail("OCR must not run for a text PDF"))
    text, source = documents.pdf_text(text_pdf())
    assert source == "pdf" and "Spring Boot" in text


def test_scanned_pdf_is_read_with_ocr():
    text, source = documents.pdf_text(scanned_pdf())
    assert source == "ocr"
    squashed = documents.squash(text)
    for phrase in ("spring boot", "postgresql", "docker", "sqlite"):
        assert phrase in squashed


def test_blank_scan_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(documents, "_ocr_pdf", lambda raw: "")
    with pytest.raises(ApiError) as caught:
        documents.pdf_text(text_pdf(["x"]))
    assert caught.value.status_code == 422 and "OCR" in caught.value.detail


def test_not_a_pdf_is_rejected():
    with pytest.raises(ApiError):
        documents.pdf_text(b"hello")


def test_ocr_single_column_reads_top_to_bottom():
    result = ocr_result([(50, 500, 40, "second"), (50, 500, 10, "first"), (50, 500, 70, "third")])
    assert documents._ocr_lines(result, 600) == ["first", "second", "third"]


def test_ocr_sidebar_layout_reads_column_by_column():
    """A narrow left sidebar (about a third of the page) must not interleave with the main column."""
    lines = [(20, 1200, 0, "Header spanning both columns")]
    for i in range(6):
        lines.append((20, 330, 100 + i * 40, f"side {i}"))
        lines.append((420, 1150, 100 + i * 40, f"main {i}"))
    lines.append((900, 1150, 98, "May 2026"))  # right-aligned date, a pixel above its row
    order = documents._ocr_lines(ocr_result(lines), 1240)
    assert order[0] == "Header spanning both columns"
    assert order[1:7] == [f"side {i}" for i in range(6)]
    assert order[7:9] == ["main 0", "May 2026"]
    assert order[9:] == [f"main {i}" for i in range(1, 6)]
