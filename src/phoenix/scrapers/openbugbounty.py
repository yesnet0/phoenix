"""Open Bug Bounty scraper — Tier 3 (Playwright, Cloudflare-protected).

Open Bug Bounty is a non-profit coordinated vulnerability disclosure platform.
Even with Playwright, the site presents a Cloudflare challenge page.
Leaderboard scraping is currently unavailable without captcha bypass.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

BASE_URL = "https://www.openbugbounty.org"
LEADERBOARD_URL = f"{BASE_URL}/researchers/"
PROFILE_BASE = f"{BASE_URL}/researchers"


@register_scraper("openbugbounty")
class OpenBugBountyScraper(PlaywrightScraper):
    platform_name = "openbugbounty"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        log.warning(
            "openbugbounty_cloudflare_blocked",
            msg="Open Bug Bounty leaderboard is behind Cloudflare challenge. "
                "Requires stealth browser or captcha-solving integration.",
        )
        return []

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        page = await self._new_page()

        try:
            profile_url = f"{PROFILE_BASE}/{username}/"
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            raw_data: dict = {}
            rank = None
            score = None
            finding_count = None
            fixed_count = None

            # Extract total reports/bugs
            report_match = re.search(r"(?:total\s*(?:reports?|bugs?|vulnerabilit))\s*\n?\s*([\d,]+)", body, re.IGNORECASE)
            if report_match:
                finding_count = int(report_match.group(1).replace(",", ""))
                raw_data["total_reports"] = finding_count

            # Extract fixed count
            fixed_match = re.search(r"(?:fixed)\s*\n?\s*([\d,]+)", body, re.IGNORECASE)
            if fixed_match:
                fixed_count = int(fixed_match.group(1).replace(",", ""))
                raw_data["fixed_count"] = fixed_count

            # Extract rank
            rank_match = re.search(r"(?:rank|position)\s*\n?\s*#?(\d+)", body, re.IGNORECASE)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            # Extract score/points
            score_match = re.search(r"(?:score|points|reputation)\s*\n?\s*([\d,]+)", body, re.IGNORECASE)
            if score_match:
                score = float(score_match.group(1).replace(",", ""))
                raw_data["score"] = score

            # Extract display name
            name_match = re.search(r"^([^\n]{3,50})", body)
            display_name = name_match.group(1).strip() if name_match else username

            external_links = await self._get_all_links(page, exclude_domain="openbugbounty.org")
            social_links = extract_social_links(body, external_links)

            acceptance_rate = None
            if finding_count and fixed_count:
                acceptance_rate = fixed_count / finding_count

            profile = PlatformProfile(
                platform_name=self.platform_name,
                username=username,
                display_name=display_name,
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
