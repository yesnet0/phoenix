"""YesWeHack scraper — Tier 1 (Public REST API).

Uses the YesWeHack public API for rankings and hunter profiles.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

API_BASE = "https://api.yeswehack.com"


@register_scraper("yeswehack")
class YesWeHackScraper(ApiScraper):
    platform_name = "yeswehack"

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        entries: list[LeaderboardEntry] = []
        page = 1
        per_page = min(max_entries, 50)

        while len(entries) < max_entries:
            resp = await self._get(
                f"{API_BASE}/rankings",
                params={"page": page, "nb_entries": per_page},
            )
            data = resp.json()

            items = data.get("items", data.get("rankings", []))
            if not items:
                break

            for item in items:
                username = item.get("username", item.get("hunter_username", ""))
                if not username:
                    continue
                entries.append(
                    LeaderboardEntry(
                        username=username,
                        rank=item.get("rank", item.get("position")),
                        score=item.get("score", item.get("reputation", item.get("points"))),
                        profile_url=f"https://yeswehack.com/hunters/{username}",
                        extra={
                            k: item[k]
                            for k in ("bug_count", "collab_count", "country")
                            if k in item
                        },
                    )
                )
                if len(entries) >= max_entries:
                    break

            pagination = data.get("pagination", {})
            if page >= pagination.get("nb_pages", page):
                break
            page += 1

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        resp = await self._get(f"{API_BASE}/hunters/{username}")
        user = resp.json()

        if not user or not user.get("username"):
            raise ValueError(f"YesWeHack user not found: {username}")

        bio = user.get("bio", "") or user.get("description", "") or ""
        urls = []
        if user.get("website"):
            urls.append(user["website"])
        if user.get("twitter"):
            urls.append(f"https://twitter.com/{user['twitter']}")
        if user.get("github"):
            urls.append(f"https://github.com/{user['github']}")

        social_links = extract_social_links(bio, urls)

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=user.get("name", user.get("display_name", "")),
            bio=bio,
            location=user.get("country", user.get("location", "")),
            profile_url=f"https://yeswehack.com/hunters/{username}",
            social_links=social_links,
            badges=[b.get("label", b.get("name", str(b))) for b in user.get("badges", [])],
            skill_tags=user.get("skills", []),
            join_date=user.get("created_at", user.get("joined_at")),
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=user.get("score", user.get("reputation", user.get("points"))),
            global_rank=user.get("rank", user.get("position")),
            finding_count=user.get("bug_count", user.get("report_count")),
            acceptance_rate=user.get("acceptance_rate"),
            raw_data={
                k: user[k]
                for k in (
                    "collab_count", "kudos_count", "streak",
                    "critical_count", "high_count", "medium_count", "low_count",
                )
                if k in user
            },
        )

        return profile, snapshot
