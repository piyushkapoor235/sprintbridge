"""Roster CSV parsing and validation (docs/api-contract.md §3, roster preview).

Header (exact): student_id,name,email,branch,batch,cgpa. Limits: 1 MB, 100 rows.
The same parser runs for preview and for commit; commit never trusts a preview.
"""

import csv
import io
import re
from decimal import Decimal, InvalidOperation

from app.errors import ApiError
from app.schemas.university import RosterPreview, RosterRowInput, RowError

HEADER = ["student_id", "name", "email", "branch", "batch", "cgpa"]
MAX_BYTES = 1024 * 1024
MAX_ROWS = 100
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def parse_roster(raw: bytes) -> RosterPreview:
    if len(raw) > MAX_BYTES:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "The CSV must be 1 MB or smaller.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ApiError(422, "VALIDATION_ERROR", "The file must be UTF-8 CSV.") from exc

    reader = csv.reader(io.StringIO(text))
    header = [h.strip().lower() for h in next(reader, [])]
    if header != HEADER:
        raise ApiError(
            422, "VALIDATION_ERROR", f"The header must be exactly: {','.join(HEADER)}", {"file": "Invalid header."}
        )

    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if len(rows) > MAX_ROWS:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", f"The CSV may contain at most {MAX_ROWS} rows.")

    valid: list[RosterRowInput] = []
    errors: list[RowError] = []
    seen: set[str] = set()
    for number, cells in enumerate(rows, start=1):
        row_errors = _validate(number, cells, seen)
        if len(cells) == len(HEADER) and cells[0].strip():
            seen.add(cells[0].strip())  # track every ID, so a later duplicate is caught even if this row is invalid
        if row_errors:
            errors.extend(row_errors)
        else:
            student_id, name, email, branch, batch, cgpa = (c.strip() for c in cells)
            valid.append(
                RosterRowInput(
                    student_id=student_id,
                    name=name,
                    email=email.lower(),
                    branch=branch.lower(),
                    batch=int(batch),
                    cgpa=Decimal(cgpa).quantize(Decimal("0.01")) if cgpa else None,
                )
            )
    return RosterPreview(total_rows=len(rows), valid_rows=valid, errors=errors)


def _validate(number: int, cells: list[str], seen: set[str]) -> list[RowError]:
    if len(cells) != len(HEADER):
        return [RowError(row=number, field=None, message=f"Expected {len(HEADER)} columns, found {len(cells)}.")]
    student_id, name, email, branch, batch, cgpa = (c.strip() for c in cells)
    problems: list[tuple[str, str]] = []
    if not student_id or len(student_id) > 64:
        problems.append(("student_id", "student_id is required (max 64 characters)."))
    elif student_id in seen:
        problems.append(("student_id", "Duplicate student_id in file."))
    if not name or len(name) > 200:
        problems.append(("name", "name is required (max 200 characters)."))
    if not _EMAIL.match(email):
        problems.append(("email", "email is not valid."))
    if not branch or len(branch) > 64:
        problems.append(("branch", "branch is required (max 64 characters)."))
    if not batch.isdigit() or not 2000 <= int(batch) <= 2100:
        problems.append(("batch", "batch must be a year between 2000 and 2100."))
    if cgpa:
        try:
            value = Decimal(cgpa)
            if not Decimal(0) <= value <= Decimal(10) or value.as_tuple().exponent < -2:
                problems.append(("cgpa", "CGPA must be between 0 and 10 with at most 2 decimals."))
        except InvalidOperation:
            problems.append(("cgpa", "CGPA must be a number."))
    return [RowError(row=number, field=f, message=m) for f, m in problems]


def field_errors(preview: RosterPreview) -> dict[str, str]:
    return {f"row {e.row}.{e.field or 'row'}": e.message for e in preview.errors}
