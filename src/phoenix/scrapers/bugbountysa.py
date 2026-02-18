"""BugBountySA scraper — Tier 3 (Playwright, regional platform).

Leaderboard: https://bugbounty.sa/leaderboard
Profile: https://bugbounty.sa/researcher/{username}

The leaderboard is behind a login wall. Authentication is required
to access researcher ranking data.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://bugbounty.sa/leaderboard"
PROFILE_BASE = "https://bugbounty.sa/researcher"


@register_scraper("bugbountysa")
class BugbountysaScraper(PlaywrightScraper):
    platform_name = "bugbountysa"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        raise ConnectionError(
            "BugBountySA leaderboard requires authentication. "
            "Cannot scrape without logged-in session credentials."
        )

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        page = await self._new_page()

        try:
            profile_url = f"{PROFILE_BASE}/{username}"
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            raw_data: dict = {}
            rank = None
            score = None
            finding_count = None
            acceptance_rate = None

            rank_match = re.search(r"(?:Rank|Position)\s*[:#]?\s*(\d+)", body, re.I)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            score_match = re.search(r"(?:Points|Score|Reputation)\s*[:#]?\s*([\d,]+)", body, re.I)
            if score_match:
                score = float(score_match.group(1).replace(",", ""))
                raw_data["score"] = score

            bugs_match = re.search(r"(?:Reports?|Bugs?|Findings?|Vulnerabilit(?:y|ies))\s*[:#]?\s*(\d+)", body, re.I)
            if bugs_match:
                finding_count = int(bugs_match.group(1))
                raw_data["finding_count"] = finding_count

            acc_match = re.search(r"(?:Acceptance|Valid)\s*(?:Rate)?\s*[:#]?\s*([\d.]+)\s*%", body, re.I)
            if acc_match:
                acceptance_rate = float(acc_match.group(1))
                raw_data["acceptance_rate"] = acceptance_rate

            location = ""
            loc_match = re.search(r"(?:Location|Country|From)\s*[:#]?\s*([A-Za-z\s,]+?)(?:\n|$)", body, re.I)
            if loc_match:
                location = loc_match.group(1).strip()

            external_links = await self._get_all_links(page, exclude_domain="bugbounty.sa")
            social_links = extract_social_links(body, external_links)

            profile = PlatformProfile(
                platform_name=self.platform_name,
                username=username,
                display_name=username,
                location=location,
                profile_url=profile_url,
                social_links=social_links,
            )

            snapshot = ProfileSnapshot(
                profile_id=profile.id,
                overall_score=score,
                global_rank=rank,
                finding_count=finding_count,
                acceptance_rate=acceptance_rate,
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()
