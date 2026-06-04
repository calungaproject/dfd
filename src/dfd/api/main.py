"""DFD API — FastAPI application.

Serves the REST API for the dashboard and static SPA files.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dfd.api.auth import AuthMiddleware
from dfd.api.routes import (
    analysis_runs,
    chat,
    collect,
    conversations,
    costs,
    health,
    pipeline_types,
    runs,
    stats,
    taxonomy,
)
from dfd.common import db, s3
from dfd.common.config import Settings

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down resources."""
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        db.init_pool(database_url)
        logger.info("Database pool initialized")
    else:
        logger.warning(
            "DATABASE_URL not set — API will fail on DB queries"
        )
    settings = Settings()
    s3.init_s3(settings.s3_endpoint_url or None)
    logger.info("S3 client initialized")
    yield
    db.close_pool()
    logger.info("Database pool closed")


app = FastAPI(
    title="DFD API",
    description=(
        "Dumpster Fire Diving — CI Pipeline Failure Analysis"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(AuthMiddleware)

app.include_router(health.router)
app.include_router(pipeline_types.router)
app.include_router(runs.router)
app.include_router(stats.router)
app.include_router(taxonomy.router)
app.include_router(analysis_runs.router)
app.include_router(costs.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(collect.router)

if STATIC_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(STATIC_DIR), html=True),
        name="static",
    )
