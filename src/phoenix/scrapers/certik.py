"""CertiK scraper — Tier 3 (Playwright, React SPA, security audit platform).

Leaderboard: https://skynet.certik.com/leaderboards/bug-bounty
Profile: https://skynet.certik.com/community/{username}
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://skynet.certik.com/leaderboards/bug-bounty"
PROFILE_BASE = "https://skynet.certik.com/community"


@register_scraper("certik")
class CertikScraper(PlaywrightScraper):
    platform_name = "certik"

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
                            score_match = re.match(
                                r"^[\$]?([\d,]+(?:\.\d+)?)\s*(?:pts|points|bounty)?$",
                                lines[i + offset],
                                re.I,
                            )
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

            log.info("certik_leaderboard_scraped", entries=len(entries))

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
            earnings = None

            rank_match = re.search(r"(?:Rank|Position|#)\s*[:#]?\s*(\d+)", body, re.I)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            score_match = re.search(r"(?:Points|Score|Reputation)\s*[:#]?\s*([\d,]+)", body, re.I)
            if score_match:
                score = float(score_match.group(1).replace(",", ""))
                raw_data["score"] = score

            earnings_match = re.search(r"(?:Earned|Bounty|Reward)\s*[:#]?\s*\$?([\d,]+(?:\.\d+)?)", body, re.I)
            if earnings_match:
                earnings = float(earnings_match.group(1).replace(",", ""))
                raw_data["earnings"] = earnings

            bugs_match = re.search(r"(?:Reports?|Bugs?|Findings?|Vulnerabilit(?:y|ies))\s*[:#]?\s*(\d+)", body, re.I)
            if bugs_match:
                finding_count = int(bugs_match.group(1))
                raw_data["finding_count"] = finding_count

            # Web3-specific: audits count
            audits_match = re.search(r"(?:Audits?)\s*[:#]?\s*(\d+)", body, re.I)
            if audits_match:
                raw_data["audits"] = int(audits_match.group(1))

            for severity in ["Critical", "High", "Medium", "Low"]:
                sev_match = re.search(rf"{severity}\s*[:#]?\s*(\d+)", body, re.I)
                if sev_match:
                    raw_data[severity.lower()] = int(sev_match.group(1))

            bio = ""
            bio_match = re.search(r"(?:Bio|About)\s*[:#]?\s*(.+?)(?:\n|$)", body, re.I)
            if bio_match:
                bio = bio_match.group(1).strip()

            external_links = await self._get_all_links(page, exclude_domain="certik.com")
            social_links = extract_social_links(body, external_links)

            badges: list[str] = []
            badge_patterns = ["Top Hunter", "Security Expert", "Verified", "Elite"]
            for badge in badge_patterns:
                if badge.lower() in body.lower():
                    badges.append(badge)

            profile = PlatformProfile(
                platform_name=self.platform_name,
                username=username,
                display_name=username,
                bio=bio,
                profile_url=profile_url,
                social_links=social_links,
                badges=badges,
            )

            snapshot = ProfileSnapshot(
                profile_id=profile.id,
                overall_score=score,
                global_rank=rank,
                total_earnings=earnings,
                finding_count=finding_count,
                critical_count=raw_data.get("critical"),
                high_count=raw_data.get("high"),
                medium_count=raw_data.get("medium"),
                low_count=raw_data.get("low"),
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()
