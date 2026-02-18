"""Code4rena scraper — Tier 3 (Playwright, Next.js RSC).

Code4rena (C4) is a competitive audit platform for smart contracts.
The site uses Next.js React Server Components. Playwright is required.

Body text pattern (after header section ending with "Gas"):
  Each entry is 9 lines: rank, username, $earnings,
  then 6 count lines: total, high, solo_high, med, solo_med, gas.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://code4rena.com/leaderboard"
PROFILE_BASE = "https://code4rena.com/@"


@register_scraper("code4rena")
class Code4renaScraper(PlaywrightScraper):
    platform_name = "code4rena"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            lines = [l.strip() for l in body.split("\n") if l.strip()]

            # Find where data starts: after the "Gas" header line
            start_idx = 0
            for idx, line in enumerate(lines):
                if line == "Gas":
                    start_idx = idx + 1
                    break

            if start_idx == 0:
                # Fallback: look for the header sequence
                for idx, line in enumerate(lines):
                    if line == "(Solo)" and idx + 1 < len(lines):
                        # Could be Med (Solo) or High (Solo); take last one
                        start_idx = idx + 1

            # Parse blocks: rank, username, $earnings, total, high, solo_high, med, solo_med, gas
            i = start_idx
            while i < len(lines) and len(entries) < max_entries:
                # Look for a rank number (digit-only line)
                if not re.match(r"^\d+$", lines[i]):
                    i += 1
                    continue

                rank = int(lines[i])

                # Next line should be username (non-digit, non-$ line)
                if i + 1 >= len(lines):
                    break
                username = lines[i + 1]
                if re.match(r"^\d+$", username) or username.startswith("$"):
                    i += 1
                    continue

                # Next line should be $earnings
                earnings = None
                score = None
                raw_data: dict = {}
                if i + 2 < len(lines):
                    earn_match = re.match(r"^\$([\d,]+(?:\.\d+)?)$", lines[i + 2])
                    if earn_match:
                        earnings = float(earn_match.group(1).replace(",", ""))
                        score = earnings

                # Parse 6 count lines: total, high, solo_high, med, solo_med, gas
                count_names = ["total", "high", "solo_high", "med", "solo_med", "gas"]
                for j, name in enumerate(count_names):
                    line_idx = i + 3 + j
                    if line_idx < len(lines) and re.match(r"^\d+$", lines[line_idx]):
                        raw_data[name] = int(lines[line_idx])

                entries.append(
                    LeaderboardEntry(
                        username=username,
                        rank=rank,
                        score=score,
                        profile_url=f"{PROFILE_BASE}{username}",
                    )
                )

                # Skip past this block (9 lines per entry)
                i += 9

            log.info("code4rena_leaderboard_parsed", count=len(entries))

        finally:
            await page.context.close()

        return entries

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        page = await self._new_page()

        try:
            profile_url = f"{PROFILE_BASE}{username}"
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            raw_data: dict = {}
            rank = None
            score = None
            finding_count = None
            total_earnings = None

            # Extract total earnings/awards
            earn_match = re.search(r"(?:total|all.?time|awards?|earned)\s*\n?\s*\$?([\d,]+(?:\.\d+)?)", body, re.IGNORECASE)
            if earn_match:
                total_earnings = float(earn_match.group(1).replace(",", ""))
                score = total_earnings
                raw_data["total_earnings"] = total_earnings

            # Extract rank
            rank_match = re.search(r"(?:rank|position)\s*\n?\s*#?(\d+)", body, re.IGNORECASE)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            # Extract findings count
            find_match = re.search(r"(?:findings?|high\s*risk|med\s*risk)\s*\n?\s*(\d+)", body, re.IGNORECASE)
            if find_match:
                finding_count = int(find_match.group(1))
                raw_data["findings"] = finding_count

            # Extract high/medium risk counts
            high_match = re.search(r"(?:high\s*(?:risk)?)\s*\n?\s*(\d+)", body, re.IGNORECASE)
            if high_match:
                raw_data["high_risk"] = int(high_match.group(1))

            med_match = re.search(r"(?:med(?:ium)?\s*(?:risk)?)\s*\n?\s*(\d+)", body, re.IGNORECASE)
            if med_match:
                raw_data["med_risk"] = int(med_match.group(1))

            external_links = await self._get_all_links(page, exclude_domain="code4rena.com")
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
                total_earnings=total_earnings,
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()
