"""Hats Finance scraper — Tier 3 (Playwright, client-side SPA).

Hats Finance is a decentralized bug bounty protocol. The app.hats.finance
domain does not resolve via httpx. The site is a client-side SPA requiring
Playwright.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://app.hats.finance/leaderboard"
APP_URL = "https://app.hats.finance"


@register_scraper("hatsfinance")
class HatsFinanceScraper(PlaywrightScraper):
    platform_name = "hatsfinance"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            # Parse leaderboard rows from rendered body text
            lines = body.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Try rank + username/address + payout pattern
                # Hats may show Ethereum addresses or handles
                match = re.match(r"^(\d+)\s+(0x[\da-fA-F]+|\S+)\s+\$?([\d,]+(?:\.\d+)?)", line)
                if match:
                    rank = int(match.group(1))
                    username = match.group(2)
                    score_str = match.group(3).replace(",", "")
                    try:
                        score = float(score_str)
                    except ValueError:
                        score = None

                    entries.append(
                        LeaderboardEntry(
                            username=username,
                            rank=rank,
                            score=score,
                            profile_url=f"{APP_URL}/profile/{username}",
                        )
                    )

                    if len(entries) >= max_entries:
                        break

            log.info("hatsfinance_leaderboard_parsed", count=len(entries))

        finally:
            await page.context.close()

        return entries

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        """Scrape profile page if available, otherwise return minimal data."""
        page = await self._new_page()

        try:
            profile_url = f"{APP_URL}/profile/{username}"
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            raw_data: dict = {}
            score = None
            finding_count = None

            # Extract total payout
            payout_match = re.search(r"(?:total\s*payout|earned|rewards?)\s*\n?\s*\$?([\d,]+(?:\.\d+)?)", body, re.IGNORECASE)
            if payout_match:
                score = float(payout_match.group(1).replace(",", ""))
                raw_data["total_payout"] = score

            # Extract findings count
            find_match = re.search(r"(?:findings?|reports?|submissions?)\s*\n?\s*(\d+)", body, re.IGNORECASE)
            if find_match:
                finding_count = int(find_match.group(1))
                raw_data["findings"] = finding_count

            # Format display name for addresses
            display_name = username
            if username.startswith("0x") and len(username) > 10:
                display_name = f"{username[:6]}...{username[-4:]}"

            external_links = await self._get_all_links(page, exclude_domain="hats.finance")
            social_links = extract_social_links(body, external_links)

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
                finding_count=finding_count,
                total_earnings=score,
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()
