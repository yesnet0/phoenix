"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from phoenix.core.database import close_driver
from phoenix.core.logging import setup_logging

# Import scrapers to trigger registration
import phoenix.scrapers.hackerone  # noqa: F401
import phoenix.scrapers.bugcrowd  # noqa: F401
import phoenix.scrapers.intigriti  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield
    await close_driver()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Phoenix",
        description="Bug bounty researcher skills graph API",
        version="0.1.0",
        lifespan=lifespan,
    )

    from phoenix.api.routes import health, scrape, researchers

    app.include_router(health.router, tags=["health"])
    app.include_router(scrape.router, prefix="/scrape", tags=["scrape"])
    app.include_router(researchers.router, prefix="/researchers", tags=["researchers"])

    return app


app = create_app()
