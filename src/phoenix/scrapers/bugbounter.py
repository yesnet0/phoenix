"""BugBounter scraper — Tier 3 (Playwright, SPA).

Leaderboard: https://app.bugbounter.com/public-top-bounters
Profile: https://app.bugbounter.com/researcher/{username}

Body text pattern (after "Reputation" header):
  Triplets of: rank_number, username, score
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://app.bugbounter.com/public-top-bounters"
PROFILE_BASE = "https://app.bugbounter.com/researcher"


@register_scraper("bugbounter")
class BugbounterScraper(PlaywrightScraper):
    platform_name = "bugbounter"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            # SPA takes 10-15s to render leaderboard data after headers load
            body = await self._get_body_text(page, wait_ms=15000)

            lines = [l.strip() for l in body.split("\n") if l.strip()]

            # Find the "Reputation" header marker
            start_idx = 0
            for idx, line in enumerate(lines):
                if line == "Reputation":
                    start_idx = idx + 1
                    break

            if start_idx == 0:
                log.warning("bugbounter_no_reputation_header_found")
                return entries

            # After "Reputation", data comes in triplets: rank, username, score
            i = start_idx
            while i + 2 < len(lines) and len(entries) < max_entries:
                # rank line (digit only)
                if not re.match(r"^\d+$", lines[i]):
                    i += 1
                    continue

                rank = int(lines[i])
                username = lines[i + 1]

                # Validate username is not a number
                if re.match(r"^\d+$", username):
                    i += 1
                    continue

                # Score line
                score = None
                score_match = re.match(r"^([\d,]+)$", lines[i + 2])
                if score_match:
                    score = float(score_match.group(1).replace(",", ""))

                entries.append(
                    LeaderboardEntry(
                        username=username,
                        rank=rank,
                        score=score,
                        profile_url=f"{PROFILE_BASE}/{username}",
                    )
                )

                i += 3

            log.info("bugbounter_leaderboard_scraped", entries=len(entries))

        finally:
            await page.context.close()

        return entries

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

            score_match = re.search(r"(?:Points|Score|Reputation|Bounty)\s*[:#]?\s*([\d,]+)", body, re.I)
            if score_match:
                score = float(score_match.group(1).replace(",", ""))
                raw_data["score"] = score

            bugs_match = re.search(r"(?:Reports?|Bugs?|Findings?)\s*[:#]?\s*(\d+)", body, re.I)
            if bugs_match:
                finding_count = int(bugs_match.group(1))
                raw_data["finding_count"] = finding_count

            acc_match = re.search(r"(?:Acceptance|Valid)\s*(?:Rate)?\s*[:#]?\s*([\d.]+)\s*%", body, re.I)
            if acc_match:
                acceptance_rate = float(acc_match.group(1))
                raw_data["acceptance_rate"] = acceptance_rate

            bio = ""
            bio_match = re.search(r"(?:Bio|About)\s*[:#]?\s*(.+?)(?:\n|$)", body, re.I)
            if bio_match:
                bio = bio_match.group(1).strip()

            location = ""
            loc_match = re.search(r"(?:Location|Country|From)\s*[:#]?\s*([A-Za-z\s,]+?)(?:\n|$)", body, re.I)
            if loc_match:
                location = loc_match.group(1).strip()

            external_links = await self._get_all_links(page, exclude_domain="bugbounter.com")
            social_links = extract_social_links(body, external_links)

            profile = PlatformProfile(
                platform_name=self.platform_name,
                username=username,
                display_name=username,
                bio=bio,
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
