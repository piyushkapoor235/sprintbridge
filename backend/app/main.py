"""FastAPI application: one modular monolith (docs/architecture.md §5)."""

import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_error_handlers
from app.routers import applications, drives, health, me, mentors, opportunities, skills, university, ventures

logger = logging.getLogger("sprintbridge")
if not logger.handlers:  # uvicorn configures only its own loggers
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="SprintBridge API", version="0.1.0")

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        # Reuse a well-formed incoming ID; otherwise mint one. Log no headers, bodies or tokens.
        incoming = request.headers.get("x-request-id", "")
        request.state.request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        logger.info(
            "request_id=%s method=%s route=%s status=%s duration_ms=%.1f",
            request.state.request_id,
            request.method,
            getattr(route, "path", request.url.path),
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    register_error_handlers(app)

    for module in (health, me, opportunities, applications, university, drives, mentors, skills, ventures):
        app.include_router(module.router, prefix="/api")

    return app


app = create_app()
