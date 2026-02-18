"""HackenProof scraper — Tier 3 (Playwright, Cloudflare-protected).

HackenProof is a Web3-focused bug bounty platform. Even with Playwright,
the site presents a Cloudflare challenge page requiring captcha solving.
Leaderboard scraping is currently unavailable without stealth/captcha bypass.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://hackenproof.com/leaderboard"
PROFILE_BASE = "https://hackenproof.com/hackers"


@register_scraper("hackenproof")
class HackenProofScraper(PlaywrightScraper):
    platform_name = "hackenproof"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        log.warning(
            "hackenproof_cloudflare_blocked",
            msg="HackenProof leaderboard is behind Cloudflare challenge. "
                "Requires stealth browser or captcha-solving integration.",
        )
        return []

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

            # Extract reputation/score
            rep_match = re.search(r"(?:reputation|score|points)\s*\n?\s*([\d,]+)", body, re.IGNORECASE)
            if rep_match:
                score = float(rep_match.group(1).replace(",", ""))
                raw_data["reputation"] = score

            # Extract rank
            rank_match = re.search(r"(?:rank|position)\s*\n?\s*#?(\d+)", body, re.IGNORECASE)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            # Extract bug/report count
            bug_match = re.search(r"(?:bugs?|reports?|findings?)\s*\n?\s*(\d+)", body, re.IGNORECASE)
            if bug_match:
                finding_count = int(bug_match.group(1))
                raw_data["finding_count"] = finding_count

            external_links = await self._get_all_links(page, exclude_domain="hackenproof.com")
            social_links = extract_social_links(body, external_links)

            profile = PlatformProfile(
                platform_name=self.platform_name,
                username=username,
                display_name=username,
                profile_url=profile_url,
                social_links=social_links,
            )

            snapshot = ProfileSnapshot(
                profile_id=profile.id,
                overall_score=score,
                global_rank=rank,
                finding_count=finding_count,
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()
