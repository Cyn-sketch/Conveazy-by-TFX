import logging
import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .ai.engine import AIUnavailable
from .config import get_settings
from .db import Base, get_engine
from .deps import csrf_guard
from .routers import account, ai, auth, checkins, profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("conveazy")


def create_app(create_tables: bool = True) -> FastAPI:
    settings = get_settings()
    settings.validate_for_production()
    app = FastAPI(title="CONVEAZY by TFX API", version="0.1.0", dependencies=[Depends(csrf_guard)],
                  docs_url="/api/docs" if settings.env != "production" else None, openapi_url="/api/openapi.json")

    if create_tables:
        Base.metadata.create_all(get_engine())

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        # Logs method, path, status and timing only. Never bodies: they contain intimate content.
        rid = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        log.info("rid=%s %s %s %s %.0fms", rid, request.method, request.url.path, response.status_code,
                 (time.perf_counter() - start) * 1000)
        return response

    @app.exception_handler(AIUnavailable)
    async def _ai_unavailable(_: Request, exc: AIUnavailable):
        return JSONResponse(status_code=503, content={"detail": {"code": "ai_unavailable", "message": str(exc)}})

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        fields = [".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": {"code": "invalid_input", "message": "Please check: " + ", ".join(fields),
                                             "fields": fields}})

    @app.get("/api/health")
    def health():
        return {"ok": True}

    for r in (auth.router, account.router, profile.router, checkins.router, ai.router):
        app.include_router(r)
    return app


app = create_app()
