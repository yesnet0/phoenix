"""Neo4j schema initialization — constraints, indexes, and platform seed data."""

from neo4j import AsyncSession

from phoenix.core.logging import get_logger
from phoenix.models.platform import PLATFORMS

log = get_logger(__name__)

CONSTRAINTS = [
    "CREATE CONSTRAINT researcher_id IF NOT EXISTS FOR (r:Researcher) REQUIRE r.id IS UNIQUE",
    "CREATE CONSTRAINT profile_id IF NOT EXISTS FOR (p:PlatformProfile) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT profile_platform_username IF NOT EXISTS FOR (p:PlatformProfile) REQUIRE (p.platform_name, p.username) IS UNIQUE",
    "CREATE CONSTRAINT platform_name IF NOT EXISTS FOR (pl:Platform) REQUIRE pl.name IS UNIQUE",
    "CREATE CONSTRAINT skill_id IF NOT EXISTS FOR (s:Skill) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT snapshot_id IF NOT EXISTS FOR (s:ProfileSnapshot) REQUIRE s.id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX profile_username IF NOT EXISTS FOR (p:PlatformProfile) ON (p.username)",
    "CREATE INDEX profile_last_scraped IF NOT EXISTS FOR (p:PlatformProfile) ON (p.last_scraped)",
    "CREATE INDEX researcher_canonical IF NOT EXISTS FOR (r:Researcher) ON (r.canonical_name)",
    "CREATE INDEX snapshot_captured IF NOT EXISTS FOR (s:ProfileSnapshot) ON (s.captured_at)",
    "CREATE INDEX social_link IF NOT EXISTS FOR (s:SocialLink) ON (s.platform, s.handle)",
]


async def init_constraints(session: AsyncSession) -> None:
    for stmt in CONSTRAINTS:
        try:
            await session.run(stmt)
            await log.ainfo("constraint_created", statement=stmt)
        except Exception as e:
            await log.awarning("constraint_skipped", statement=stmt, error=str(e))


async def init_indexes(session: AsyncSession) -> None:
    for stmt in INDEXES:
        try:
            await session.run(stmt)
            await log.ainfo("index_created", statement=stmt)
        except Exception as e:
            await log.awarning("index_skipped", statement=stmt, error=str(e))


async def seed_platforms(session: AsyncSession) -> None:
    for p in PLATFORMS:
        await session.run(
            """
            MERGE (pl:Platform {name: $name})
            SET pl.display_name = $display_name,
                pl.base_url = $base_url,
                pl.scraper_tier = $scraper_tier,
                pl.enabled = $enabled
            """,
            name=p.name,
            display_name=p.display_name,
            base_url=p.base_url,
            scraper_tier=p.scraper_tier.value,
            enabled=p.enabled,
        )
    await log.ainfo("platforms_seeded", count=len(PLATFORMS))


async def init_schema(session: AsyncSession) -> None:
    """Run full schema initialization."""
    await init_constraints(session)
    await init_indexes(session)
    await seed_platforms(session)
