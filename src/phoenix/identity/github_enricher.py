"""GitHub profile enricher for identity resolution.

For profiles that have a GitHub social link, fetch the GitHub user profile
via the public API to discover additional social handles (Twitter, blog,
company, email) that can be used for cross-platform identity matching.
"""

import httpx
from neo4j import AsyncSession

from phoenix.core.logging import get_logger
from phoenix.identity.resolver import PLATFORM_ACCOUNTS
from phoenix.models.researcher import SocialLink, SocialPlatform
from phoenix.schema.queries import upsert_social_link
from phoenix.scrapers.utils.normalizer import normalize_handle

log = get_logger(__name__)

GITHUB_API = "https://api.github.com/users"


async def enrich_from_github(session: AsyncSession) -> int:
    """Fetch GitHub profiles for all github social links and add discovered socials.

    Returns count of new social links added.
    """
    # Find all github social links with their profile IDs
    result = await session.run(
        """
        MATCH (p:PlatformProfile)-[:HAS_SOCIAL]->(sl:SocialLink {platform: "github"})
        RETURN p.id AS profile_id, sl.handle AS github_handle
        """
    )
    github_links = [dict(rec) async for rec in result]

    if not github_links:
        log.info("github_enricher_no_links")
        return 0

    # Filter out platform accounts
    links_to_check = [
        link for link in github_links
        if ("github", link["github_handle"]) not in PLATFORM_ACCOUNTS
    ]

    log.info("github_enricher_start", profiles=len(links_to_check))

    added = 0
    async with httpx.AsyncClient(
        headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "Phoenix/1.0"},
        timeout=15.0,
    ) as client:
        for link in links_to_check:
            try:
                resp = await client.get(f"{GITHUB_API}/{link['github_handle']}")
                if resp.status_code == 404:
                    continue
                if resp.status_code == 403:
                    log.warning("github_rate_limited")
                    break
                resp.raise_for_status()

                data = resp.json()
                profile_id = link["profile_id"]

                # Twitter handle
                twitter = data.get("twitter_username")
                if twitter and ("twitter", normalize_handle(twitter)) not in PLATFORM_ACCOUNTS:
                    sl = SocialLink(
                        platform=SocialPlatform.TWITTER,
                        handle=normalize_handle(twitter),
                        raw_value=f"github_enriched:{twitter}",
                    )
                    await upsert_social_link(session, profile_id, sl)
                    added += 1
                    log.info("github_enriched_twitter", profile_id=profile_id, handle=twitter)

                # Blog URL → may contain useful domain
                blog = data.get("blog")
                if blog and blog.strip():
                    blog = blog.strip()
                    if not blog.startswith("http"):
                        blog = f"https://{blog}"
                    # Check for twitter/linkedin in blog URL
                    if "twitter.com" in blog or "x.com" in blog:
                        handle = blog.rstrip("/").split("/")[-1]
                        if handle and ("twitter", normalize_handle(handle)) not in PLATFORM_ACCOUNTS:
                            sl = SocialLink(
                                platform=SocialPlatform.TWITTER,
                                handle=normalize_handle(handle),
                                raw_value=f"github_blog:{blog}",
                            )
                            await upsert_social_link(session, profile_id, sl)
                            added += 1
                    elif "linkedin.com/in/" in blog:
                        handle = blog.rstrip("/").split("/")[-1]
                        if handle:
                            sl = SocialLink(
                                platform=SocialPlatform.LINKEDIN,
                                handle=normalize_handle(handle),
                                raw_value=f"github_blog:{blog}",
                            )
                            await upsert_social_link(session, profile_id, sl)
                            added += 1

                # Email
                email = data.get("email")
                if email and ("email", email.lower()) not in PLATFORM_ACCOUNTS:
                    sl = SocialLink(
                        platform=SocialPlatform.EMAIL,
                        handle=email.lower(),
                        raw_value=f"github_enriched:{email}",
                    )
                    await upsert_social_link(session, profile_id, sl)
                    added += 1
                    log.info("github_enriched_email", profile_id=profile_id, email=email)

            except httpx.HTTPStatusError:
                continue
            except Exception as e:
                log.warning("github_enricher_error", handle=link["github_handle"], error=str(e))
                continue

    log.info("github_enricher_done", checked=len(links_to_check), added=added)
    return added
