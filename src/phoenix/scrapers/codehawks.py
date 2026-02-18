"""CodeHawks scraper — Tier 3 (Playwright, SvelteKit SPA).

CodeHawks (by Cyfrin) is a competitive smart contract audit platform.
The __data.json endpoint is unreliable; Playwright rendering is required.

Body text pattern (after header row):
  rank (digit-only line)
  username (next line)
  $earnings\txp\thigh\tmedium\tlow (tab-separated line)
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

BASE_URL = "https://www.codehawks.com"
LEADERBOARD_URL = f"{BASE_URL}/leaderboard"


@register_scraper("codehawks")
class CodeHawksScraper(PlaywrightScraper):
    platform_name = "codehawks"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            lines = [l.strip() for l in body.split("\n") if l.strip()]

            # Pattern: digit-only line (rank), username line, then
            # tab-separated "$earnings\txp\thigh\tmedium\tlow" line
            i = 0
            while i < len(lines) and len(entries) < max_entries:
                # Look for rank (digit-only line)
                if not re.match(r"^\d+$", lines[i]):
                    i += 1
                    continue

                rank = int(lines[i])

                # Next line is username
                if i + 1 >= len(lines):
                    break
                username = lines[i + 1]
                if re.match(r"^\d+$", username) or username.startswith("$"):
                    i += 1
                    continue

                # Next line has tab-separated data: $earnings\txp\thigh\tmedium\tlow
                score = None
                earnings = None
                raw_data: dict = {}
                if i + 2 < len(lines):
                    data_line = lines[i + 2]
                    parts = re.split(r"\t+", data_line)
                    if parts and parts[0].startswith("$"):
                        earn_match = re.match(r"\$([\d,]+(?:\.\d+)?)", parts[0])
                        if earn_match:
                            earnings = float(earn_match.group(1).replace(",", ""))
                            score = earnings
                    if len(parts) >= 2:
                        try:
                            raw_data["xp"] = int(parts[1])
                        except ValueError:
                            pass

                entries.append(
                    LeaderboardEntry(
                        username=username,
                        rank=rank,
                        score=score,
                        profile_url=f"{BASE_URL}/profile/{username}",
                    )
                )

                # Skip past this block (3 lines per entry)
                i += 3

            log.info("codehawks_leaderboard_parsed", count=len(entries))

        finally:
            await page.context.close()

        return entries

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        page = await self._new_page()

        try:
            profile_url = f"{BASE_URL}/profile/{username}"
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            raw_data: dict = {}
            rank = None
            score = None
            finding_count = None
            total_earnings = None

            earn_match = re.search(r"\$([\d,]+(?:\.\d+)?)", body)
            if earn_match:
                total_earnings = float(earn_match.group(1).replace(",", ""))
                score = total_earnings
                raw_data["earnings"] = total_earnings

            rank_match = re.search(r"(?:rank|position)\s*\n?\s*#?(\d+)", body, re.IGNORECASE)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            find_match = re.search(r"(?:findings?|high\s*risk|med\s*risk)\s*\n?\s*(\d+)", body, re.IGNORECASE)
            if find_match:
                finding_count = int(find_match.group(1))
                raw_data["findings"] = finding_count

            external_links = await self._get_all_links(page, exclude_domain="codehawks.com")
            social_links = extract_social_links(body, external_links)

            profile = PlatformProfile(
                platform_name=self.platform_name,
                username=username,
                display_name=username,
                bio="",
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
