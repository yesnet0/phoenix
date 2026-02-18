"""Initialize Neo4j schema and seed platform data."""

import asyncio

from phoenix.core.database import close_driver, get_session
from phoenix.core.logging import setup_logging, get_logger
from phoenix.schema.init_schema import init_schema

log = get_logger(__name__)


async def main() -> None:
    setup_logging()
    log.info("init_db_start")
    async with get_session() as session:
        await init_schema(session)
    await close_driver()
    log.info("init_db_complete")


if __name__ == "__main__":
    asyncio.run(main())
