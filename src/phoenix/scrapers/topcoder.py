"""Topcoder scraper — Tier 1 (Public REST API).

Topcoder has a well-documented public API at api.topcoder.com/v5.
Currently UNAVAILABLE — the API returns 503 on all endpoints.
"""

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper

log = get_logger(__name__)

API_BASE = "https://api.topcoder.com/v5"
SITE_URL = "https://www.topcoder.com"


@register_scraper("topcoder")
class TopcoderScraper(ApiScraper):
    platform_name = "topcoder"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        log.warning(
            "topcoder_api_unavailable",
            msg="Topcoder API is currently unavailable (503 on all endpoints).",
        )
        return []

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        raise ConnectionError("Topcoder API is currently unavailable (503)")
