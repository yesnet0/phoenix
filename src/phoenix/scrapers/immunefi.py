"""Immunefi scraper — Tier 3 (Playwright, React SPA).

Immunefi is a Web3 bug bounty platform. No discoverable API exists
(all tried endpoints return 404). It's a React SPA requiring Playwright.

Body text pattern (each entry is a block of labeled lines):
  rank_number / username / "Name" / score_number / "Whitehat Score" /
  "$earnings" / "Total Earnings" / paid_count / "Paid Reports"
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://immunefi.com/leaderboard/"
PROFILE_BASE = "https://immunefi.com/profile"


@register_scraper("immunefi")
class ImmunefiScraper(PlaywrightScraper):
    platform_name = "immunefi"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            lines = [l.strip() for l in body.split("\n") if l.strip()]

            # Pattern: rank(digit), username(non-digit), "Name",
            #          score(digit), "Whitehat Score",
            #          $earnings, "Total Earnings",
            #          paid(digit), "Paid Reports"
            i = 0
            while i < len(lines) and len(entries) < max_entries:
                # Look for a rank number (digit-only line)
                if not re.match(r"^\d+$", lines[i]):
                    i += 1
                    continue

                rank = int(lines[i])

                # Next non-digit line should be username
                if i + 1 >= len(lines):
                    break
                username = lines[i + 1]
                if re.match(r"^\d+$", username):
                    i += 1
                    continue

                # Expect "Name" label at i+2
                if i + 2 >= len(lines) or lines[i + 2] != "Name":
                    i += 1
                    continue

                # Score at i+3
                score = None
                if i + 3 < len(lines):
                    score_match = re.match(r"^([\d,]+)$", lines[i + 3])
                    if score_match:
                        score = float(score_match.group(1).replace(",", ""))

                # Expect "Whitehat Score" at i+4, earnings at i+5, "Total Earnings" at i+6
                earnings = None
                if i + 5 < len(lines):
                    earn_match = re.match(r"^\$([\d,]+(?:\.\d+)?)$", lines[i + 5])
                    if earn_match:
                        earnings = float(earn_match.group(1).replace(",", ""))

                # Paid reports at i+7
                paid_reports = None
                if i + 7 < len(lines):
                    paid_match = re.match(r"^(\d+)$", lines[i + 7])
                    if paid_match:
                        paid_reports = int(paid_match.group(1))

                entries.append(
                    LeaderboardEntry(
                        username=username,
                        rank=rank,
                        score=score,
                        profile_url=f"{PROFILE_BASE}/{username}/",
                    )
                )

                # Skip past this block (9 lines per entry)
                i += 9

            log.info("immunefi_leaderboard_parsed", count=len(entries))

        finally:
            await page.context.close()

        return entries

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
            total_earnings = None

            # Extract total paid out
            paid_match = re.search(r"(?:total\s+paid|earned|payout)\s*\n?\s*\$?([\d,]+(?:\.\d+)?)", body, re.IGNORECASE)
            if paid_match:
                total_earnings = float(paid_match.group(1).replace(",", ""))
                score = total_earnings
                raw_data["total_paid"] = total_earnings

            # Extract rank
            rank_match = re.search(r"(?:rank|position)\s*\n?\s*#?(\d+)", body, re.IGNORECASE)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            # Extract bug count
            bug_match = re.search(r"(?:bugs?|reports?|findings?)\s*\n?\s*(\d+)", body, re.IGNORECASE)
            if bug_match:
                finding_count = int(bug_match.group(1))
                raw_data["finding_count"] = finding_count

            external_links = await self._get_all_links(page, exclude_domain="immunefi.com")
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
