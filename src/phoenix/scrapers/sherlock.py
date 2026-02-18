"""Sherlock scraper — Tier 1 (REST API).

Sherlock is a Web3 audit contest platform. The /auditors endpoint returns
a flat JSON array of all auditor usernames. No individual profile endpoint
is available.
"""

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

API_BASE = "https://mainnet-contest.sherlock.xyz"
APP_URL = "https://app.sherlock.xyz"


@register_scraper("sherlock")
class SherlockScraper(ApiScraper):
    platform_name = "sherlock"

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        """Fetch auditor usernames from /auditors (returns flat JSON array)."""
        try:
            resp = await self._get(f"{API_BASE}/auditors")
            data = resp.json()
        except Exception as e:
            log.warning("sherlock_auditors_failed", error=str(e))
            return []

        if not isinstance(data, list):
            log.warning("sherlock_unexpected_format", type=type(data).__name__)
            return []

        entries: list[LeaderboardEntry] = []
        for i, username in enumerate(data[:max_entries]):
            if not isinstance(username, str) or not username:
                continue
            entries.append(
                LeaderboardEntry(
                    username=username,
                    rank=i + 1,
                    score=None,
                    profile_url=f"{APP_URL}/audits/leaderboard",
                )
            )

        log.info("sherlock_leaderboard_fetched", total_auditors=len(data), returned=len(entries))
        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        """Return minimal profile data (no individual profile endpoint exists)."""
        # Verify the username exists in the auditors list
        try:
            resp = await self._get(f"{API_BASE}/auditors")
            auditors = resp.json()
        except Exception as e:
            raise ValueError(f"Sherlock API unavailable: {e}") from e

        if not isinstance(auditors, list) or username not in auditors:
            raise ValueError(f"Sherlock auditor not found: {username}")

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=username,
            bio="",
            profile_url=f"{APP_URL}/audits/leaderboard",
            social_links=[],
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            raw_data={"source": "auditors_list"},
        )

        return profile, snapshot
