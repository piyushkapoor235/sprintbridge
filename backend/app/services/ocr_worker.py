"""OCR for scanned resumes, run as a short-lived child process (`python -m app.services.ocr_worker`).

OCR models need a few hundred MB while they run. In a child process that memory is returned to the
system as soon as the job ends, and if a small server runs out of memory the kernel kills this
process, not the API. Reads PDF bytes on stdin; writes JSON on stdout:
{"pages": [{"width": float, "lines": [[x0, x1, y, text], ...]}, ...]}

`--warm` downloads the models (run at build time so the first scan is not slow).
"""

import json
import sys

MAX_PAGES = 5
RENDER_SCALE = 1.5  # ~108 dpi: body text stays readable; memory grows with image area


def engine():
    from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

    # Default text detector + English mobile recognizer, one thread, no rotation classifier: about
    # 475 MB peak on a resume page in testing, and it keeps spaces and commas ("Java, Python, SQL")
    # that the smaller v4 English recognizer dropped.
    return RapidOCR(params={
        "Global.use_cls": False,
        "Global.log_level": "error",
        "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.MOBILE, "Rec.lang_type": LangRec.EN,
        "Rec.rec_batch_num": 1,
        "EngineConfig.onnxruntime.intra_op_num_threads": 1,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    })


def read_pdf(raw: bytes) -> dict:
    import pypdfium2 as pdfium

    ocr = engine()
    pdf = pdfium.PdfDocument(raw)
    pages = []
    try:
        for index in range(min(len(pdf), MAX_PAGES)):
            image = pdf[index].render(scale=RENDER_SCALE).to_pil()
            result = ocr(image)
            lines = []
            for box, text in zip(result.boxes if result.txts else [], result.txts or []):
                xs, ys = [float(p[0]) for p in box], [float(p[1]) for p in box]
                lines.append([min(xs), max(xs), min(ys), text])
            pages.append({"width": float(image.width), "lines": lines})
    finally:
        pdf.close()
    return {"pages": pages}


if __name__ == "__main__":
    if "--warm" in sys.argv:
        engine()
    else:
        json.dump(read_pdf(sys.stdin.buffer.read()), sys.stdout)
