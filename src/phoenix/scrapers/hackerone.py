"""HackerOne scraper — Tier 1 (GraphQL API).

Uses the HackerOne GraphQL endpoint with CSRF token auth.
Schema references:
  - github.com/Hacker0x01/helpful-recon-data/blob/master/schema.graphql
  - github.com/hackermondev/hackerone-tracker
"""

import httpx

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot, SocialLink, SocialPlatform
from phoenix.scrapers.base import LeaderboardEntry, PlatformScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links, normalize_handle
from phoenix.scrapers.utils.retry import scrape_retry
from phoenix.scrapers.utils.stealth import random_ua
from phoenix.scrapers.utils.timing import jittered_delay

log = get_logger(__name__)

GRAPHQL_URL = "https://hackerone.com/graphql"

LEADERBOARD_QUERY = """
query LeaderboardQuery($first: Int, $after: String) {
  leaderboard_entries(key: ALL_TIME_REPUTATION, first: $first, after: $after) {
    total_count
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        ... on AllTimeReputationLeaderboardEntry {
          rank
          reputation
          user {
            username
            name
          }
        }
      }
    }
  }
}
"""

PROFILE_QUERY = """
query UserProfileQuery($username: String!) {
  user(username: $username) {
    id
    username
    name
    bio
    intro
    website
    location
    country
    created_at
    reputation
    rank
    signal
    signal_percentile
    impact
    impact_percentile
    cleared
    verified
    hackerone_triager
    twitter_handle
    github_handle
    linkedin_handle
    leaderboard_entry(key: ALL_TIME_REPUTATION) {
      ... on AllTimeReputationLeaderboardEntry {
        rank
        reputation
      }
    }
  }
}
"""


@register_scraper("hackerone")
class HackerOneScraper(PlatformScraper):
    platform_name = "hackerone"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": random_ua(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
            follow_redirects=True,
        )
    @scrape_retry
    async def _graphql(self, query: str, variables: dict | None = None) -> dict:
        resp = await self._client.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables or {}},
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            log.warning("graphql_errors", errors=data["errors"])
        return data.get("data", {})

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        entries: list[LeaderboardEntry] = []
        cursor: str | None = None
        page_size = min(max_entries, 100)

        while len(entries) < max_entries:
            data = await self._graphql(
                LEADERBOARD_QUERY,
                {"first": page_size, "after": cursor},
            )
            lb = data.get("leaderboard_entries", {})
            edges = lb.get("edges", [])

            if not edges:
                break

            for edge in edges:
                node = edge.get("node", {})
                user = node.get("user", {})
                username = user.get("username", "")
                if not username:
                    continue
                entries.append(
                    LeaderboardEntry(
                        username=username,
                        rank=node.get("rank"),
                        score=node.get("reputation"),
                        profile_url=f"https://hackerone.com/{username}",
                        extra={"signal": user.get("signal"), "impact": user.get("impact")},
                    )
                )
                if len(entries) >= max_entries:
                    break

            page_info = lb.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
            await jittered_delay()

        return entries

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        data = await self._graphql(PROFILE_QUERY, {"username": username})
        user = data.get("user", {})

        if not user:
            raise ValueError(f"HackerOne user not found: {username}")

        # Build social links from dedicated fields + bio/website extraction
        social_links: list[SocialLink] = []
        if user.get("twitter_handle"):
            handle = normalize_handle(user["twitter_handle"])
            social_links.append(SocialLink(platform=SocialPlatform.TWITTER, handle=handle, raw_value=user["twitter_handle"]))
        if user.get("github_handle"):
            handle = normalize_handle(user["github_handle"])
            social_links.append(SocialLink(platform=SocialPlatform.GITHUB, handle=handle, raw_value=user["github_handle"]))
        if user.get("linkedin_handle"):
            handle = normalize_handle(user["linkedin_handle"])
            social_links.append(SocialLink(platform=SocialPlatform.LINKEDIN, handle=handle, raw_value=user["linkedin_handle"]))

        # Also extract from bio + website
        urls = [user["website"]] if user.get("website") else []
        bio_links = extract_social_links(user.get("bio", "") + " " + user.get("intro", ""), urls)
        # Merge without duplicating
        existing = {(l.platform, l.handle) for l in social_links}
        for link in bio_links:
            if (link.platform, link.handle) not in existing:
                social_links.append(link)

        badges: list[str] = []
        if user.get("cleared"):
            badges.append("cleared")
        if user.get("verified"):
            badges.append("verified")
        if user.get("hackerone_triager"):
            badges.append("triager")

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=user.get("name", ""),
            bio=user.get("bio", ""),
            location=user.get("location", ""),
            profile_url=f"https://hackerone.com/{username}",
            social_links=social_links,
            badges=badges,
            join_date=user.get("created_at"),
        )

        # Get rank from nested leaderboard_entry if available
        lb_entry = user.get("leaderboard_entry") or {}
        global_rank = lb_entry.get("rank") or user.get("rank")

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=user.get("reputation"),
            global_rank=global_rank,
            signal_percentile=user.get("signal_percentile"),
            impact_percentile=user.get("impact_percentile"),
            raw_data={
                "signal": user.get("signal"),
                "impact": user.get("impact"),
                "country": user.get("country"),
                "cleared": user.get("cleared"),
                "verified": user.get("verified"),
            },
        )

        return profile, snapshot

    async def close(self) -> None:
        await self._client.aclose()
