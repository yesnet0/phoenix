"""Strict identity resolution pipeline.

Links profiles across platforms using exact social key matches only.
No fuzzy matching. No speculation. Full audit trail.
"""

from neo4j import AsyncSession

from phoenix.core.logging import get_logger
from phoenix.models.researcher import IdentityLink, PlatformProfile, SocialPlatform
from phoenix.schema.queries import (
    create_researcher,
    ensure_researchers_for_orphans,
    find_profiles_by_social,
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


async def resolve_identity(session: AsyncSession, profile: PlatformProfile) -> str | None:
    """Attempt to link a profile to a Researcher via exact social key matches.

    Returns the researcher_id if linked, None if profile stays standalone.
    """
    if not profile.social_links:
        log.info("no_social_links", profile_id=profile.id, username=profile.username)
        return None

    # Check if this profile is already linked
    existing_researcher = await get_researcher_by_profile(session, profile.id)
    if existing_researcher:
        return existing_researcher

    # Search for matching profiles via each authoritative social key
    for link in profile.social_links:
        if link.platform not in AUTHORITATIVE_KEYS:
            continue

        # Skip platform-level social accounts (shared by all profiles on a platform)
        if (link.platform.value, link.handle) in PLATFORM_ACCOUNTS:
            continue

        matches = await find_profiles_by_social(session, link.platform.value, link.handle)

        # Filter out self-matches
        other_profiles = [m for m in matches if m["profile_id"] != profile.id]

        if not other_profiles:
            continue

        # Found a match — check if any matched profile already has a researcher
        for match in other_profiles:
            matched_researcher = await get_researcher_by_profile(session, match["profile_id"])
            if matched_researcher:
                # Link our profile to the existing researcher
                identity_link = IdentityLink(
                    key_type=link.platform.value,
                    key_value=link.handle,
                )
                await link_profile_to_researcher(session, profile.id, matched_researcher, identity_link)
                log.info(
                    "identity_linked_existing",
                    profile_id=profile.id,
                    researcher_id=matched_researcher,
                    key=f"{link.platform.value}:{link.handle}",
                )
                return matched_researcher

        # No researcher exists yet — create one and link both profiles
        best_name = profile.display_name or profile.username
        researcher_id = await create_researcher(session, best_name)

        # Link the new profile
        identity_link = IdentityLink(
            key_type=link.platform.value,
            key_value=link.handle,
        )
        await link_profile_to_researcher(session, profile.id, researcher_id, identity_link)

        # Link the matched profile(s)
        for match in other_profiles:
            match_link = IdentityLink(
                key_type=link.platform.value,
                key_value=link.handle,
            )
            await link_profile_to_researcher(session, match["profile_id"], researcher_id, match_link)

        log.info(
            "identity_created",
            researcher_id=researcher_id,
            profiles_linked=1 + len(other_profiles),
            key=f"{link.platform.value}:{link.handle}",
        )
        return researcher_id

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
