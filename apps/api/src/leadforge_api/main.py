"""FastAPI app entrypoint — add scraper health and metrics routes."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from leadforge_config import get_settings
from starlette.exceptions import HTTPException as StarletteHTTPException

from leadforge_api.core.errors import AppError
from leadforge_api.core.logging import configure_logging, get_logger
from leadforge_api.core.queue import close_pool
from leadforge_api.routes import (
    admin,
    analytics,
    auth,
    businesses,
    exports,
    leads,
    search_jobs,
    social_profiles,
)
from leadforge_api.routes.scrapers import router as scrapers_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("leadforge-api")
    log = get_logger("leadforge-api")
    log.info("api.starting")
    yield
    log.info("api.stopping")
    await close_pool()


app = FastAPI(
    title="LeadForge API",
    version="1.0.0",
    description="Queue-driven enrichment pipeline for discovering, enriching, scoring, exporting business leads.",
    lifespan=lifespan,
)


def _cors_config() -> tuple[list[str], bool]:
    """Resolve allowed origins + credentials.

    A wildcard origin cannot be combined with credentials (browsers reject it),
    so ``*`` explicitly disables credentials. In development without
    ``CORS_ORIGINS`` we default to the local web app.
    """
    raw = os.getenv("CORS_ORIGINS", "").strip()
    requested = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if "*" in requested:
        return ["*"], False
    if requested:
        return requested, True
    if not get_settings().is_production:
        return ["http://localhost:3000", "http://127.0.0.1:3000"], True
    return [], False


_cors_origins, _cors_credentials = _cors_config()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(search_jobs.router, prefix=API_PREFIX)
app.include_router(businesses.router, prefix=API_PREFIX)
app.include_router(leads.router, prefix=API_PREFIX)
app.include_router(exports.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(social_profiles.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)

# Scraper health and metrics (no auth for /metrics)
app.include_router(scrapers_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict:
    return {"success": True, "service": "leadforge-api"}


@app.get("/health")
async def health() -> dict:
    return {"success": True, "service": "leadforge-api"}


@app.get("/health/scrapers")
async def scraper_health() -> dict:
    """Dedicated scraper health endpoint (no auth)."""
    from leadforge_scraper_core.metrics import get_scraper_health

    health = await get_scraper_health()
    return {"success": True, "service": "leadforge-scrapers", "sources": health}


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint (no auth)."""
    from leadforge_scraper_core.metrics import get_metrics_bytes, get_metrics_content_type

    return Response(content=get_metrics_bytes(), media_type=get_metrics_content_type())


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "context": exc.context,
            },
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        code = detail.get("code", "ERROR")
        message = detail.get("message", "Error")
    else:
        code = "UNAUTHORIZED" if exc.status_code == 401 else "ERROR"
        message = str(detail) if detail else "Error"
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": code, "message": message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request",
                "context": {"errors": exc.errors()},
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
    get_logger("leadforge-api").error("api.unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"},
        },
    )


def run() -> None:
    import uvicorn
    from leadforge_config import get_settings

    settings = get_settings()
    uvicorn.run(
        "leadforge_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=not settings.is_production,
    )


if __name__ == "__main__":
    run()
