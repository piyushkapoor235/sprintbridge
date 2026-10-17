"""The endpoint table in docs/api-contract.md and the running app must list the same operations."""

import re
from pathlib import Path

from app.main import app

CONTRACT = Path(__file__).resolve().parents[2] / "docs" / "api-contract.md"
ROW = re.compile(r"^\| (GET|POST|PATCH|DELETE) \| (/api/\S+) \|", re.MULTILINE)


def test_contract_table_matches_app_routes():
    documented = set(ROW.findall(CONTRACT.read_text()))
    served = {
        (method.upper(), path)
        for path, item in app.openapi()["paths"].items()
        for method in item
    }
    assert documented == served, {
        "documented_only": sorted(documented - served),
        "served_only": sorted(served - documented),
    }


def test_every_operation_except_health_requires_bearer_auth():
    for path, item in app.openapi()["paths"].items():
        for method, op in item.items():
            if path == "/api/health":
                assert "security" not in op
            else:
                assert op.get("security"), f"{method.upper()} {path} is missing bearer auth"
