"""EpicBounties scraper — Tier 3 (Playwright, SPA).

Leaderboard: https://app.epicbounties.com/hunter-ranking
Profile: https://app.epicbounties.com/hunter/{username}
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://app.epicbounties.com/hunter-ranking"
PROFILE_BASE = "https://app.epicbounties.com/hunter"


@register_scraper("epicbounties")
class EpicbountiesScraper(PlaywrightScraper):
    platform_name = "epicbounties"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        log.warning(
            "epicbounties_site_down",
            msg="EpicBounties domain has invalid SSL certificate (net::ERR_CERT_COMMON_NAME_INVALID). "
                "Site appears to be down or decommissioned.",
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

            earnings_match = re.search(r"(?:Earned|Bounty|Reward|Earnings)\s*[:#]?\s*\$?([\d,]+(?:\.\d+)?)", body, re.I)
            if earnings_match:
                raw_data["earnings"] = float(earnings_match.group(1).replace(",", ""))

            for severity in ["Critical", "High", "Medium", "Low"]:
                sev_match = re.search(rf"{severity}\s*[:#]?\s*(\d+)", body, re.I)
                if sev_match:
                    raw_data[severity.lower()] = int(sev_match.group(1))

            external_links = await self._get_all_links(page, exclude_domain="epicbounties.com")
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
                acceptance_rate=acceptance_rate,
                critical_count=raw_data.get("critical"),
                high_count=raw_data.get("high"),
                medium_count=raw_data.get("medium"),
                low_count=raw_data.get("low"),
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()
