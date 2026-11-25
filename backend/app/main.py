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



def _setup_error_app(message: str) -> FastAPI:
    """When config or the database is wrong, answer every request with a clear JSON reason
    instead of crashing, so the sign-up page can show what to fix. Never includes secret values."""
    broken = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @broken.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def _explain(path: str):
        return JSONResponse(status_code=503, content={"detail": {"code": "server_setup", "message": message}})

    return broken


def _safe_reason(exc: Exception) -> str:
    from pydantic import ValidationError
    from sqlalchemy.exc import SQLAlchemyError
    if isinstance(exc, ValidationError):
        fields = sorted({(lambda n: n if n.startswith("CONVEAZY_") else "CONVEAZY_" + n)(str(e["loc"][0]).upper())
                         for e in exc.errors() if e.get("loc")})
        return "Server setup problem: check these environment variables: " + ", ".join(fields) + "."
    if isinstance(exc, SQLAlchemyError):
        import os
        import re
        source = next((n for n in ("CONVEAZY_DATABASE_URL", "DATABASE_URL", "POSTGRES_URL") if os.environ.get(n)), None) \
            or next((n for n in sorted(os.environ) if n.endswith(("_DATABASE_URL", "_POSTGRES_URL"))), None)
        if source is None:
            return ("Server setup problem: no database is set. Connect a Neon database in Vercel's Storage tab "
                    "(or set CONVEAZY_DATABASE_URL) and redeploy.")
        detail = str(getattr(exc, "orig", None) or exc).strip().splitlines()[0][:220]
        detail = re.sub(r"[a-z+]+://\S+", "<url>", detail)          # never echo a connection string
        detail = re.sub(r"(password|user)=\S+", r"\1=<hidden>", detail)
        return (f"Server setup problem: can't reach the database set in {source}. Reason: {detail} "
                "Check that variable in Vercel (pooled Neon connection string) and redeploy.")
    if isinstance(exc, RuntimeError) and str(exc).startswith("Unsafe production config"):
        return "Server setup problem: " + str(exc).split(": ", 1)[1] + "."
    return "Server setup problem: the API couldn't start. Check the backend logs in Vercel."


def _build() -> FastAPI:
    try:
        return create_app()
    except Exception as exc:  # noqa: BLE001 - startup must never crash without telling the user why
        log.exception("startup failed")
        return _setup_error_app(_safe_reason(exc))


# Keep this a plain top-level assignment: Vercel looks for `app` here.
app = _build()
