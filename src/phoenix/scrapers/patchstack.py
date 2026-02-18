"""Patchstack scraper — Tier 1 (REST API).

Patchstack is a WordPress vulnerability disclosure platform with
a researcher leaderboard at vdp-api.patchstack.com.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

API_URL = "https://vdp-api.patchstack.com/researchers"
SITE_URL = "https://patchstack.com"


@register_scraper("patchstack")
class PatchstackScraper(ApiScraper):
    platform_name = "patchstack"

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        """Fetch researchers from the paginated VDP API (25 per page)."""
        entries: list[LeaderboardEntry] = []
        page = 1
        per_page = 25

        while len(entries) < max_entries:
            try:
                resp = await self._get(API_URL, params={"page": page})
                data = resp.json()
            except Exception as e:
                log.warning("patchstack_api_failed", page=page, error=str(e))
                break

            items = data.get("data", [])
            if not items:
                break

            for i, item in enumerate(items):
                if len(entries) >= max_entries:
                    break

                uuid = item.get("uuid", "")
                name = item.get("name", "").strip().lstrip("\ufeff")
                if not uuid:
                    continue

                # Use name as username if available, fall back to UUID
                display = name if name else uuid

                entries.append(
                    LeaderboardEntry(
                        username=display,
                        rank=((page - 1) * per_page) + i + 1,
                        score=item.get("xp"),
                        profile_url=f"{SITE_URL}/database/researcher/{uuid}",
                        extra={
                            "uuid": uuid,
                            "name": name,
                            "xp": item.get("xp"),
                            "level": item.get("level"),
                            "rank": item.get("rank"),
                        },
                    )
                )

            page += 1

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        """Fetch researcher profile from the list API using UUID.

        There is no separate profile endpoint; we search the paginated list
        for the matching UUID.
        """
        user: dict = {}
        page = 1

        # Search through pages to find the user by UUID
        while page <= 20:  # Cap at 20 pages (500 researchers)
            try:
                resp = await self._get(API_URL, params={"page": page})
                data = resp.json()
            except Exception:
                break

            items = data.get("data", [])
            if not items:
                break

            for item in items:
                if item.get("uuid") == username:
                    user = item
                    break

            if user:
                break
            page += 1

        if not user:
            raise ValueError(f"Patchstack profile not found: {username}")

        name = user.get("name", "")
        twitter_url = user.get("twitter", "") or ""
        github_url = user.get("github", "") or ""
        website_url = user.get("website", "") or ""
        urls = [u for u in (twitter_url, github_url, website_url) if u]
        social_links = extract_social_links("", urls)

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=name,
            bio="",
            profile_url=f"{SITE_URL}/database/researcher/{username}",
            social_links=social_links,
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=user.get("xp"),
            global_rank=user.get("rank"),
            raw_data={
                "xp": user.get("xp"),
                "level": user.get("level"),
                "rank": user.get("rank"),
                "name": name,
            },
        )

        return profile, snapshot
