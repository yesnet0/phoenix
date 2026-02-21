"""Identity resolution pipeline.

Links profiles across platforms using:
1. Exact social key matches (github, twitter, email, linkedin)
2. Same-username matching across different platforms

Full audit trail via IdentityLink nodes.
"""

from neo4j import AsyncSession

from phoenix.core.logging import get_logger
from phoenix.models.researcher import IdentityLink, PlatformProfile, SocialPlatform
from phoenix.schema.queries import (
    create_researcher,
    ensure_researchers_for_orphans,
    find_profiles_by_social,
    find_profiles_by_username,
    get_researcher_by_profile,
    link_profile_to_researcher,
)

log = get_logger(__name__)

# Only resolve on these authoritative key types
AUTHORITATIVE_KEYS = {
    SocialPlatform.GITHUB,
    SocialPlatform.TWITTER,
    SocialPlatform.EMAIL,
    SocialPlatform.LINKEDIN,
}

# Platform-level social accounts that must NOT be used for identity resolution.
# These are shared across all profiles on a platform and cause false merges.
PLATFORM_ACCOUNTS: set[tuple[str, str]] = {
    # Twitter/X accounts belonging to platforms
    ("twitter", "immunefi"),
    ("twitter", "asymmetric_re"),
    ("twitter", "hackenproof"),
    ("twitter", "yeswehack"),
    ("twitter", "bugaborty"),
    ("twitter", "code4rena"),
    ("twitter", "codehawks"),
    ("twitter", "sheraborty"),
    ("twitter", "huntr_ai"),
    ("twitter", "pabortystack"),
    ("twitter", "safevuln"),
    ("twitter", "bugcrowd"),
    ("twitter", "intigriti"),
    ("twitter", "hackerone"),
    ("twitter", "vulbox"),
    ("twitter", "hacktify"),
    ("twitter", "hacktify_"),
    ("twitter", "bugrapofficial"),
    ("twitter", "habortyfinance"),
    ("twitter", "chainlink"),
    ("twitter", "starknet"),
    ("twitter", "openzeppelin"),
    ("twitter", "cantaborpen"),
    ("twitter", "thegaborph"),
    # GitHub accounts belonging to platforms
    ("github", "immunefi"),
    ("github", "cyfrin"),
    ("github", "code-423n4"),
    ("github", "sherlock-audit"),
    ("github", "hats-finance"),
    ("github", "huntr-dev"),
    ("github", "patchstack"),
    # Emails belonging to platforms
    ("email", "info@hacktify.eu"),
    ("email", "support@mail.safevuln.com"),
    ("email", "partner@vulbox.com"),
    ("email", "support@bugcrowd.com"),
    ("email", "support@hackerone.com"),
    ("email", "contact@yeswehack.com"),
    ("email", "mkt@vulbox.com"),
    ("email", "service@vulbox.com"),
}

# Generic usernames that should NOT be used for username-based matching
GENERIC_USERNAMES = {
    "admin", "test", "user", "anonymous", "unknown", "null", "undefined",
    "default", "root", "guest", "hacker", "researcher", "security",
    "bug", "hunter", "private", "private user",
}


async def _link_to_existing_or_create(
    session: AsyncSession,
    profile: PlatformProfile,
    matches: list[dict],
    key_type: str,
    key_value: str,
) -> str | None:
    """Given a profile and cross-platform matches, link them under one researcher."""
    # Check if any matched profile already has a researcher
    for match in matches:
        matched_researcher = await get_researcher_by_profile(session, match["profile_id"])
        if matched_researcher:
            identity_link = IdentityLink(key_type=key_type, key_value=key_value)
            await link_profile_to_researcher(session, profile.id, matched_researcher, identity_link)
            log.info(
                "identity_linked_existing",
                profile_id=profile.id,
                researcher_id=matched_researcher,
                key=f"{key_type}:{key_value}",
            )
            return matched_researcher

    # No researcher exists yet — create one and link all
    best_name = profile.display_name or profile.username
    researcher_id = await create_researcher(session, best_name)

    identity_link = IdentityLink(key_type=key_type, key_value=key_value)
    await link_profile_to_researcher(session, profile.id, researcher_id, identity_link)

    for match in matches:
        match_link = IdentityLink(key_type=key_type, key_value=key_value)
        await link_profile_to_researcher(session, match["profile_id"], researcher_id, match_link)

    log.info(
        "identity_created",
        researcher_id=researcher_id,
        profiles_linked=1 + len(matches),
        key=f"{key_type}:{key_value}",
    )
    return researcher_id


async def resolve_identity(session: AsyncSession, profile: PlatformProfile) -> str | None:
    """Attempt to link a profile to a Researcher via exact social key matches.

    Returns the researcher_id if linked, None if profile stays standalone.
    """
    # Check if this profile is already linked
    existing_researcher = await get_researcher_by_profile(session, profile.id)
    if existing_researcher:
        return existing_researcher

    # Pass 1: Social key matching (authoritative)
    for link in profile.social_links:
        if link.platform not in AUTHORITATIVE_KEYS:
            continue

        if (link.platform.value, link.handle) in PLATFORM_ACCOUNTS:
            continue

        matches = await find_profiles_by_social(session, link.platform.value, link.handle)
        other_profiles = [m for m in matches if m["profile_id"] != profile.id]

        if not other_profiles:
            continue

        return await _link_to_existing_or_create(
            session, profile, other_profiles, link.platform.value, link.handle
        )

    # Pass 2: Username matching across platforms
    if profile.username.lower() not in GENERIC_USERNAMES and len(profile.username) >= 3:
        username_matches = await find_profiles_by_username(
            session, profile.username, profile.platform_name
        )
        if username_matches:
            return await _link_to_existing_or_create(
                session, profile, username_matches, "username", profile.username
            )

    log.info("no_identity_match", profile_id=profile.id, username=profile.username)
    return None


async def resolve_batch(session: AsyncSession, profiles: list[PlatformProfile]) -> int:
    """Run identity resolution on a batch of profiles. Returns count of resolutions."""
    resolved = 0
    for profile in profiles:
        result = await resolve_identity(session, profile)
        if result:
            resolved += 1

    # Create standalone Researcher nodes for any profiles still without one
    orphans_created = await ensure_researchers_for_orphans(session)
    if orphans_created:
        log.info("orphan_researchers_created", count=orphans_created)
        resolved += orphans_created

    return resolved
