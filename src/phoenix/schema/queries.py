"""Reusable Cypher query builders for Neo4j operations."""

import json
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
        raw_data=json.dumps(snapshot.raw_data),
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


async def ensure_researchers_for_orphans(session: AsyncSession) -> int:
    """Create a Researcher node for every profile that doesn't have one."""
    result = await session.run(
        """
        MATCH (p:PlatformProfile)
        WHERE NOT (p)-[:BELONGS_TO]->(:Researcher)
        WITH p
        CREATE (r:Researcher {
            id: randomUUID(),
            canonical_name: COALESCE(p.display_name, p.username),
            composite_score: 0.0,
            created_at: datetime().epochMillis,
            updated_at: datetime().epochMillis
        })
        CREATE (p)-[:BELONGS_TO]->(r)
        RETURN count(r) AS created
        """
    )
    record = await result.single()
    return record["created"] if record else 0


async def find_profiles_by_username(session: AsyncSession, username: str, exclude_platform: str) -> list[dict]:
    """Find profiles on OTHER platforms with the same username (case-insensitive)."""
    result = await session.run(
        """
        MATCH (p:PlatformProfile)
        WHERE toLower(p.username) = toLower($username)
          AND p.platform_name <> $exclude_platform
        RETURN p.id AS profile_id, p.platform_name AS platform_name, p.username AS username
        """,
        username=username,
        exclude_platform=exclude_platform,
    )
    return [dict(record) async for record in result]


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
                   location: p.location, badges: p.badges, skill_tags: p.skill_tags,
                   join_date: p.join_date, last_active: p.last_active,
                   last_scraped: p.last_scraped,
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


async def get_graph_data(session: AsyncSession) -> dict:
    """Return nodes and edges for Sigma.js graph visualization."""
    # Researcher nodes
    r_result = await session.run(
        """
        MATCH (r:Researcher)
        OPTIONAL MATCH (p:PlatformProfile)-[:BELONGS_TO]->(r)
        RETURN r.id AS id, r.canonical_name AS label, r.composite_score AS score,
               count(p) AS profile_count
        """
    )
    researcher_nodes = []
    async for rec in r_result:
        researcher_nodes.append({
            "id": rec["id"],
            "label": rec["label"],
            "type": "researcher",
            "score": rec["score"],
            "size": max(8, min(24, 8 + (rec["profile_count"] or 0) * 3)),
        })

    # Platform nodes
    pl_result = await session.run(
        """
        MATCH (pl:Platform)
        OPTIONAL MATCH (p:PlatformProfile)-[:ON_PLATFORM]->(pl)
        RETURN pl.name AS id, pl.name AS label, count(p) AS profile_count
        """
    )
    platform_nodes = []
    async for rec in pl_result:
        platform_nodes.append({
            "id": f"platform:{rec['id']}",
            "label": rec["label"],
            "type": "platform",
            "size": max(10, min(30, 10 + (rec["profile_count"] or 0))),
        })

    # Profile nodes + edges
    p_result = await session.run(
        """
        MATCH (p:PlatformProfile)-[:ON_PLATFORM]->(pl:Platform)
        OPTIONAL MATCH (p)-[:BELONGS_TO]->(r:Researcher)
        RETURN p.id AS id, p.username AS label, p.platform_name AS platform,
               r.id AS researcher_id
        """
    )
    profile_nodes = []
    edges = []
    edge_id = 0
    async for rec in p_result:
        profile_nodes.append({
            "id": rec["id"],
            "label": rec["label"],
            "type": "profile",
            "platform": rec["platform"],
            "size": 4,
        })
        edges.append({
            "id": f"e{edge_id}",
            "source": rec["id"],
            "target": f"platform:{rec['platform']}",
            "type": "on_platform",
        })
        edge_id += 1
        if rec["researcher_id"]:
            edges.append({
                "id": f"e{edge_id}",
                "source": rec["id"],
                "target": rec["researcher_id"],
                "type": "belongs_to",
            })
            edge_id += 1

    return {
        "nodes": researcher_nodes + platform_nodes + profile_nodes,
        "edges": edges,
    }


async def get_analytics(session: AsyncSession) -> dict:
    """Return aggregated dashboard statistics."""
    counts_result = await session.run(
        """
        OPTIONAL MATCH (r:Researcher)
        WITH count(r) AS researchers
        OPTIONAL MATCH (p:PlatformProfile)
        WITH researchers, count(p) AS profiles
        OPTIONAL MATCH (pl:Platform)
        WITH researchers, profiles, count(pl) AS platforms
        OPTIONAL MATCH (s:ProfileSnapshot)
        WITH researchers, profiles, platforms, count(s) AS snapshots
        OPTIONAL MATCH (sl:SocialLink)
        RETURN researchers, profiles, platforms, snapshots, count(sl) AS social_links
        """
    )
    counts_rec = await counts_result.single()
    counts = dict(counts_rec)

    top_score_result = await session.run(
        """
        MATCH (r:Researcher)
        OPTIONAL MATCH (p:PlatformProfile)-[:BELONGS_TO]->(r)
        RETURN r.id AS id, r.canonical_name AS name, r.composite_score AS score,
               count(p) AS platform_count
        ORDER BY r.composite_score DESC
        LIMIT 10
        """
    )
    top_by_score = [dict(rec) async for rec in top_score_result]

    top_earnings_result = await session.run(
        """
        MATCH (r:Researcher)<-[:BELONGS_TO]-(p:PlatformProfile)-[:HAS_SNAPSHOT]->(s:ProfileSnapshot)
        WHERE s.total_earnings IS NOT NULL
        WITH r, sum(s.total_earnings) AS total_earnings
        RETURN r.id AS id, r.canonical_name AS name, total_earnings
        ORDER BY total_earnings DESC
        LIMIT 10
        """
    )
    top_by_earnings = [dict(rec) async for rec in top_earnings_result]

    coverage_result = await session.run(
        """
        MATCH (pl:Platform)
        OPTIONAL MATCH (p:PlatformProfile)-[:ON_PLATFORM]->(pl)
        RETURN pl.name AS platform, count(p) AS profile_count
        ORDER BY profile_count DESC
        """
    )
    platform_coverage = [dict(rec) async for rec in coverage_result]

    cross_result = await session.run(
        """
        MATCH (r:Researcher)
        OPTIONAL MATCH (p:PlatformProfile)-[:BELONGS_TO]->(r)
        WITH r, count(p) AS num_platforms
        RETURN num_platforms, count(r) AS researcher_count
        ORDER BY num_platforms
        """
    )
    cross_platform = [dict(rec) async for rec in cross_result]

    return {
        "counts": counts,
        "top_by_score": top_by_score,
        "top_by_earnings": top_by_earnings,
        "platform_coverage": platform_coverage,
        "cross_platform_distribution": cross_platform,
    }


async def list_profiles(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    platform: str | None = None,
    sort_by: str = "earnings",
) -> list[dict]:
    """List profiles with latest snapshot data, optionally filtered by platform."""
    platform_filter = "AND p.platform_name = $platform" if platform else ""

    sort_map = {
        "earnings": "COALESCE(s.total_earnings, 0) DESC",
        "rank": "COALESCE(s.global_rank, 999999) ASC",
        "findings": "COALESCE(s.finding_count, 0) DESC",
        "score": "COALESCE(s.overall_score, 0) DESC",
        "username": "p.username ASC",
    }
    order = sort_map.get(sort_by, sort_map["earnings"])

    result = await session.run(
        f"""
        MATCH (p:PlatformProfile)
        WHERE true {platform_filter}
        OPTIONAL MATCH (p)-[:HAS_SNAPSHOT]->(s:ProfileSnapshot)
        WITH p, s ORDER BY s.captured_at DESC
        WITH p, head(collect(s)) AS s
        OPTIONAL MATCH (p)-[:BELONGS_TO]->(r:Researcher)
        RETURN p.id AS profile_id, p.platform_name AS platform_name,
               p.username AS username, p.display_name AS display_name,
               p.profile_url AS profile_url, p.bio AS bio,
               p.location AS location, p.badges AS badges,
               s.overall_score AS score, s.global_rank AS rank,
               s.total_earnings AS earnings, s.finding_count AS findings,
               s.critical_count AS critical, s.high_count AS high,
               s.medium_count AS medium, s.low_count AS low,
               r.id AS researcher_id, r.canonical_name AS researcher_name
        ORDER BY {order}
        SKIP $skip LIMIT $limit
        """,
        skip=skip,
        limit=limit,
        platform=platform,
    )
    return [dict(record) async for record in result]


async def get_identity_links(session: AsyncSession, researcher_id: str) -> list[dict]:
    """Get identity resolution links for a researcher."""
    result = await session.run(
        """
        MATCH (r:Researcher {id: $researcher_id})
        MATCH (il:IdentityLink)-[:LINKS]->(r)
        MATCH (il)-[:LINKS]->(p:PlatformProfile)
        RETURN il.id AS link_id, il.key_type AS key_type, il.key_value AS key_value,
               il.confidence AS confidence, il.resolved_at AS resolved_at,
               p.id AS profile_id, p.platform_name AS platform_name, p.username AS username
        ORDER BY il.resolved_at
        """,
        researcher_id=researcher_id,
    )
    return [dict(record) async for record in result]


async def get_available_platforms(session: AsyncSession) -> list[str]:
    """Get list of platforms that have profiles."""
    result = await session.run(
        """
        MATCH (p:PlatformProfile)
        RETURN DISTINCT p.platform_name AS platform
        ORDER BY platform
        """
    )
    return [record["platform"] async for record in result]


async def list_researchers_enriched(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "score",
) -> list[dict]:
    """List researchers with aggregated stats from their profiles."""
    sort_map = {
        "score": "r.composite_score DESC",
        "name": "r.canonical_name ASC",
        "platforms": "platform_count DESC",
        "earnings": "total_earnings DESC",
        "findings": "total_findings DESC",
    }
    order = sort_map.get(sort_by, sort_map["score"])

    result = await session.run(
        f"""
        MATCH (r:Researcher)
        OPTIONAL MATCH (p:PlatformProfile)-[:BELONGS_TO]->(r)
        OPTIONAL MATCH (p)-[:HAS_SNAPSHOT]->(s:ProfileSnapshot)
        WITH r, p, s ORDER BY s.captured_at DESC
        WITH r, p, head(collect(s)) AS latest_snap
        WITH r,
             collect(DISTINCT {{platform: p.platform_name, username: p.username}}) AS profiles,
             count(DISTINCT p.platform_name) AS platform_count,
             sum(COALESCE(latest_snap.total_earnings, 0)) AS total_earnings,
             sum(COALESCE(latest_snap.finding_count, 0)) AS total_findings,
             max(latest_snap.overall_score) AS top_score
        RETURN r.id AS id, r.canonical_name AS canonical_name,
               r.composite_score AS composite_score,
               profiles, platform_count, total_earnings, total_findings, top_score
        ORDER BY {order}
        SKIP $skip LIMIT $limit
        """,
        skip=skip,
        limit=limit,
    )
    return [dict(record) async for record in result]
