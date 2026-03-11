"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from phoenix.config import settings
from phoenix.core.database import close_driver
from phoenix.core.logging import setup_logging
from phoenix.scrapers.registry import discover_scrapers


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    discover_scrapers()
    yield
    await close_driver()


def create_app() -> FastAPI:
    discover_scrapers()

    app = FastAPI(
        title="Phoenix",
        description="Bug bounty researcher skills graph API",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from phoenix.api.routes import health, scrape, researchers, graph, analytics

    app.include_router(health.router, tags=["health"])
    app.include_router(scrape.router, prefix="/scrape", tags=["scrape"])
    app.include_router(researchers.router, prefix="/researchers", tags=["researchers"])
    app.include_router(graph.router, prefix="/graph", tags=["graph"])
    app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])

    return app


app = create_app()
