"""
FastAPI application.

Boot order matters: settings validate BEFORE anything binds a port, so a
misconfigured container dies loudly at startup rather than at 07:00 UTC.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api import sse
from backend.api.v1 import (
    alerts,
    compare,
    health,
    methodology,
    narratives,
    register,
    scores,
    signals,
    trust,
    vendors,
)
from backend.config import settings
from db.cache import close_redis
from db.session import dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    warnings = settings.validate_runtime()  # raises on fatal misconfiguration
    for w in warnings:
        print(f"[api] WARNING: {w}")

    from backend.jobs.schedule import is_enabled, shutdown_scheduler, start_scheduler

    if is_enabled():
        start_scheduler()

    print(f"[api] up — env={settings.environment} auth={settings.auth_mode}")
    yield

    shutdown_scheduler()
    await dispose_engine()
    await close_redis()
    print("[api] down")


app = FastAPI(
    title="Troy",
    description=(
        "Continuous ICT third-party monitoring. Produces a scored, fully-cited, "
        "tamper-evident evidence pack that ATTACHES TO a DORA Article 28(3) "
        "register — it is not itself a register of information."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    print(f"[api] unhandled on {request.url.path}: {exc!r}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal error", "path": request.url.path},
    )


P = settings.api_prefix
for r in (
    vendors.router,
    signals.router,
    scores.router,
    alerts.router,
    narratives.router,
    register.router,
    trust.router,
    methodology.router,
    compare.router,
):
    app.include_router(r, prefix=P)

app.include_router(health.router, prefix=P)
app.include_router(sse.router, prefix=P)


@app.get("/api")
async def root() -> dict:
    return {
        "name": "Troy",
        "version": "0.1.0",
        "docs": "/api/docs",
        "positioning": (
            "ICT third-party monitoring evidence pack — attaches to your "
            "Article 28(3) register."
        ),
    }


# Built React bundle, mounted last so it never shadows /api.
if settings.frontend_dist.exists():
    app.mount(
        "/", StaticFiles(directory=str(settings.frontend_dist), html=True), name="ui"
    )