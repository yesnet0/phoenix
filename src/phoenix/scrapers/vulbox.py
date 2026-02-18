"""Vulbox scraper — Tier 3 (Playwright, Chinese platform SPA).

Leaderboard: https://vulbox.com/top/season
Profile: https://vulbox.com/user/{username}
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://vulbox.com/top/season"
PROFILE_BASE = "https://vulbox.com/user"


@register_scraper("vulbox")
class VulboxScraper(PlaywrightScraper):
    platform_name = "vulbox"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page, wait_ms=8000)

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
                            score_match = re.match(r"^([\d,]+)\s*(?:pts|points|\u5206)?$", lines[i + offset], re.I)
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

            log.info("vulbox_leaderboard_scraped", entries=len(entries))

        finally:
            await page.context.close()

        return entries

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        page = await self._new_page()

        try:
            profile_url = f"{PROFILE_BASE}/{username}"
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page, wait_ms=8000)

            raw_data: dict = {}
            rank = None
            score = None
            finding_count = None
            acceptance_rate = None

            # Support Chinese labels alongside English
            rank_match = re.search(r"(?:Rank|Position|\u6392\u540d)\s*[:#\uff1a]?\s*(\d+)", body, re.I)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            score_match = re.search(
                r"(?:Points|Score|Reputation|\u79ef\u5206|\u5206\u6570)\s*[:#\uff1a]?\s*([\d,]+)",
                body,
                re.I,
            )
            if score_match:
                score = float(score_match.group(1).replace(",", ""))
                raw_data["score"] = score

            bugs_match = re.search(
                r"(?:Reports?|Bugs?|Findings?|Vulnerabilit(?:y|ies)|\u6f0f\u6d1e)\s*[:#\uff1a]?\s*(\d+)",
                body,
                re.I,
            )
            if bugs_match:
                finding_count = int(bugs_match.group(1))
                raw_data["finding_count"] = finding_count

            acc_match = re.search(r"(?:Acceptance|Valid|\u901a\u8fc7)\s*(?:Rate|\u7387)?\s*[:#\uff1a]?\s*([\d.]+)\s*%", body, re.I)
            if acc_match:
                acceptance_rate = float(acc_match.group(1))
                raw_data["acceptance_rate"] = acceptance_rate

            for severity in ["Critical", "High", "Medium", "Low"]:
                sev_match = re.search(rf"{severity}\s*[:#]?\s*(\d+)", body, re.I)
                if sev_match:
                    raw_data[severity.lower()] = int(sev_match.group(1))

            # Chinese severity labels
            for cn_label, en_key in [
                ("\u4e25\u91cd", "critical"),
                ("\u9ad8\u5371", "high"),
                ("\u4e2d\u5371", "medium"),
                ("\u4f4e\u5371", "low"),
            ]:
                sev_match = re.search(rf"{cn_label}\s*[:#\uff1a]?\s*(\d+)", body)
                if sev_match:
                    raw_data[en_key] = int(sev_match.group(1))

            external_links = await self._get_all_links(page, exclude_domain="vulbox.com")
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
