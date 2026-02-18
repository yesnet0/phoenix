"""Neo4j async connection manager."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession

from phoenix.config import settings

_driver: AsyncDriver | None = None


def _create_driver() -> AsyncDriver:
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


async def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = _create_driver()
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def reset_driver() -> AsyncDriver:
    """Force-create a fresh driver (e.g. after event loop change in Celery)."""
    global _driver
    _driver = _create_driver()
    return _driver


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    driver = await get_driver()
    async with driver.session() as session:
        yield session


async def verify_connectivity() -> bool:
    """Check if Neo4j is reachable."""
    try:
        driver = await get_driver()
        await driver.verify_connectivity()
        return True
    except Exception:
        return False
