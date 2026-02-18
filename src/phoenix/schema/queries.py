"""Reusable Cypher query builders for Neo4j operations."""

from datetime import UTC, datetime

from neo4j import AsyncSession

from phoenix.models.researcher import (
    IdentityLink,
    PlatformProfile,
    ProfileSnapshot,
    SocialLink,
)


async def upsert_profile(session: AsyncSession, profile: PlatformProfile) -> str:
    """Create or update a PlatformProfile node. Returns profile ID."""
    result = await session.run(
        """
        MERGE (p:PlatformProfile {platform_name: $platform_name, username: $username})
        ON CREATE SET p.id = $id
        SET p.display_name = $display_name,
            p.bio = $bio,
            p.location = $location,
            p.profile_url = $profile_url,
            p.badges = $badges,
            p.skill_tags = $skill_tags,
            p.join_date = $join_date,
            p.last_active = $last_active,
            p.last_scraped = $last_scraped
        WITH p
        MATCH (pl:Platform {name: $platform_name})
        MERGE (p)-[:ON_PLATFORM]->(pl)
        RETURN p.id AS id
        """,
        id=profile.id,
        platform_name=profile.platform_name,
        username=profile.username,
        display_name=profile.display_name,
        bio=profile.bio,
        location=profile.location,
        profile_url=profile.profile_url,
        badges=profile.badges,
        skill_tags=profile.skill_tags,
        join_date=profile.join_date.isoformat() if profile.join_date else None,
        last_active=profile.last_active.isoformat() if profile.last_active else None,
        last_scraped=profile.last_scraped.isoformat(),
    )
    record = await result.single()
    profile_id = record["id"]

    # Upsert social links as separate nodes
    for link in profile.social_links:
        await upsert_social_link(session, profile_id, link)

    return profile_id


async def upsert_social_link(session: AsyncSession, profile_id: str, link: SocialLink) -> None:
    await session.run(
        """
        MATCH (p:PlatformProfile {id: $profile_id})
        MERGE (s:SocialLink {platform: $platform, handle: $handle})
        SET s.raw_value = $raw_value
        MERGE (p)-[:HAS_SOCIAL]->(s)
        """,
        profile_id=profile_id,
        platform=link.platform.value,
        handle=link.handle,
        raw_value=link.raw_value,
    )


async def create_snapshot(session: AsyncSession, snapshot: ProfileSnapshot) -> str:
    """Create a ProfileSnapshot node linked to its profile."""
    await session.run(
        """
        MATCH (p:PlatformProfile {id: $profile_id})
        CREATE (s:ProfileSnapshot {
            id: $id,
            captured_at: $captured_at,
            overall_score: $overall_score,
            global_rank: $global_rank,
            total_earnings: $total_earnings,
            finding_count: $finding_count,
            critical_count: $critical_count,
            high_count: $high_count,
            medium_count: $medium_count,
            low_count: $low_count,
            signal_percentile: $signal_percentile,
            impact_percentile: $impact_percentile,
            acceptance_rate: $acceptance_rate,
            raw_data: $raw_data
        })
        CREATE (p)-[:HAS_SNAPSHOT]->(s)
        """,
        id=snapshot.id,
        profile_id=snapshot.profile_id,
        captured_at=snapshot.captured_at.isoformat(),
        overall_score=snapshot.overall_score,
        global_rank=snapshot.global_rank,
        total_earnings=snapshot.total_earnings,
        finding_count=snapshot.finding_count,
        critical_count=snapshot.critical_count,
        high_count=snapshot.high_count,
        medium_count=snapshot.medium_count,
        low_count=snapshot.low_count,
        signal_percentile=snapshot.signal_percentile,
        impact_percentile=snapshot.impact_percentile,
        acceptance_rate=snapshot.acceptance_rate,
        raw_data=str(snapshot.raw_data),
    )
    return snapshot.id


async def link_profile_to_researcher(
    session: AsyncSession, profile_id: str, researcher_id: str, link: IdentityLink
) -> None:
    """Link a profile to a researcher with an identity audit record."""
    await session.run(
        """
        MATCH (p:PlatformProfile {id: $profile_id})
        MATCH (r:Researcher {id: $researcher_id})
        MERGE (p)-[:BELONGS_TO]->(r)
        CREATE (il:IdentityLink {
            id: $link_id,
            key_type: $key_type,
            key_value: $key_value,
            confidence: $confidence,
            resolved_at: $resolved_at,
            resolved_by: $resolved_by
        })
        CREATE (il)-[:LINKS]->(p)
        CREATE (il)-[:LINKS]->(r)
        """,
        profile_id=profile_id,
        researcher_id=researcher_id,
        link_id=link.id,
        key_type=link.key_type,
        key_value=link.key_value,
        confidence=link.confidence,
        resolved_at=link.resolved_at.isoformat(),
        resolved_by=link.resolved_by,
    )


async def create_researcher(session: AsyncSession, canonical_name: str) -> str:
    """Create a new Researcher node."""
    from uuid import uuid4

    researcher_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    await session.run(
        """
        CREATE (r:Researcher {
            id: $id,
            canonical_name: $canonical_name,
            composite_score: 0.0,
            created_at: $now,
            updated_at: $now
        })
        """,
        id=researcher_id,
        canonical_name=canonical_name,
        now=now,
    )
    return researcher_id


async def find_profiles_by_social(session: AsyncSession, platform: str, handle: str) -> list[dict]:
    """Find PlatformProfile IDs that share a social link."""
    result = await session.run(
        """
        MATCH (p:PlatformProfile)-[:HAS_SOCIAL]->(s:SocialLink {platform: $platform, handle: $handle})
        RETURN p.id AS profile_id, p.platform_name AS platform_name, p.username AS username
        """,
        platform=platform,
        handle=handle,
    )
    return [dict(record) async for record in result]


async def get_researcher_by_profile(session: AsyncSession, profile_id: str) -> str | None:
    """Get researcher ID linked to a profile, if any."""
    result = await session.run(
        """
        MATCH (p:PlatformProfile {id: $profile_id})-[:BELONGS_TO]->(r:Researcher)
        RETURN r.id AS researcher_id
        """,
        profile_id=profile_id,
    )
    record = await result.single()
    return record["researcher_id"] if record else None


async def list_researchers(session: AsyncSession, skip: int = 0, limit: int = 50) -> list[dict]:
    result = await session.run(
        """
        MATCH (r:Researcher)
        OPTIONAL MATCH (p:PlatformProfile)-[:BELONGS_TO]->(r)
        RETURN r.id AS id, r.canonical_name AS canonical_name,
               r.composite_score AS composite_score,
               collect(DISTINCT {platform: p.platform_name, username: p.username}) AS profiles
        ORDER BY r.composite_score DESC
        SKIP $skip LIMIT $limit
        """,
        skip=skip,
        limit=limit,
    )
    return [dict(record) async for record in result]


async def get_researcher_detail(session: AsyncSession, researcher_id: str) -> dict | None:
    result = await session.run(
        """
        MATCH (r:Researcher {id: $id})
        OPTIONAL MATCH (p:PlatformProfile)-[:BELONGS_TO]->(r)
        OPTIONAL MATCH (p)-[:HAS_SNAPSHOT]->(s:ProfileSnapshot)
        OPTIONAL MATCH (p)-[:HAS_SOCIAL]->(sl:SocialLink)
        WITH r, p, collect(DISTINCT s) AS snapshots, collect(DISTINCT sl) AS social_links
        RETURN r.id AS id, r.canonical_name AS canonical_name,
               r.composite_score AS composite_score,
               r.created_at AS created_at,
               collect({
                   id: p.id, platform_name: p.platform_name, username: p.username,
                   display_name: p.display_name, bio: p.bio, profile_url: p.profile_url,
                   snapshots: snapshots, social_links: social_links
               }) AS profiles
        """,
        id=researcher_id,
    )
    record = await result.single()
    return dict(record) if record else None


async def search_profiles(session: AsyncSession, username: str) -> list[dict]:
    result = await session.run(
        """
        MATCH (p:PlatformProfile)
        WHERE toLower(p.username) CONTAINS toLower($username)
        OPTIONAL MATCH (p)-[:BELONGS_TO]->(r:Researcher)
        RETURN p.id AS profile_id, p.platform_name AS platform_name,
               p.username AS username, p.display_name AS display_name,
               p.profile_url AS profile_url,
               r.id AS researcher_id, r.canonical_name AS researcher_name
        LIMIT 50
        """,
        username=username,
    )
    return [dict(record) async for record in result]
