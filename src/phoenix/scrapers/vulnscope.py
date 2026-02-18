"""VulnScope scraper — Tier 3 (Playwright, SPA).

Leaderboard: https://vulnscope.com/hacker-ranking
Profile: https://vulnscope.com/hacker/{username}
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://vulnscope.com/hacker-ranking"
PROFILE_BASE = "https://vulnscope.com/hacker"


@register_scraper("vulnscope")
class VulnscopeScraper(PlaywrightScraper):
    platform_name = "vulnscope"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            lines = [l.strip() for l in body.split("\n") if l.strip()]

            for i, line in enumerate(lines):
                rank_match = re.match(r"^#?(\d+)$", line)
                if rank_match and i + 1 < len(lines):
                    rank = int(rank_match.group(1))
                    username = lines[i + 1].strip()
                    if not username or re.match(r"^[\d#]", username):
                        continue

                    score = None
                    for offset in range(2, 5):
                        if i + offset < len(lines):
                            score_match = re.match(r"^([\d,]+)\s*(?:pts|points)?$", lines[i + offset], re.I)
                            if score_match:
                                score = float(score_match.group(1).replace(",", ""))
                                break

                    entries.append(
                        LeaderboardEntry(
                            username=username,
                            rank=rank,
                            score=score,
                            profile_url=f"{PROFILE_BASE}/{username}",
                        )
                    )

                    if len(entries) >= max_entries:
                        break

            log.info("vulnscope_leaderboard_scraped", entries=len(entries))

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

            rank_match = re.search(r"(?:Rank|Position|Ranking)\s*[:#]?\s*(\d+)", body, re.I)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            score_match = re.search(r"(?:Points|Score|Reputation|Puntos)\s*[:#]?\s*([\d,]+)", body, re.I)
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

            for severity in ["Critical", "High", "Medium", "Low"]:
                sev_match = re.search(rf"{severity}\s*[:#]?\s*(\d+)", body, re.I)
                if sev_match:
                    raw_data[severity.lower()] = int(sev_match.group(1))

            location = ""
            loc_match = re.search(r"(?:Location|Country|From|Pais)\s*[:#]?\s*([A-Za-z\s,]+?)(?:\n|$)", body, re.I)
            if loc_match:
                location = loc_match.group(1).strip()

            external_links = await self._get_all_links(page, exclude_domain="vulnscope.com")
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
                critical_count=raw_data.get("critical"),
                high_count=raw_data.get("high"),
                medium_count=raw_data.get("medium"),
                low_count=raw_data.get("low"),
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()
