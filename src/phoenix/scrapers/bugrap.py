"""Bugrap scraper — Tier 3 (Playwright, Vue SPA).

Leaderboard: https://bugrap.io/whiteHats
Profile: https://bugrap.io/whiteHats/{username}
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://bugrap.io/whiteHats"
PROFILE_BASE = "https://bugrap.io/whiteHats"


@register_scraper("bugrap")
class BugrapScraper(PlaywrightScraper):
    platform_name = "bugrap"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            lines = [l.strip() for l in body.split("\n") if l.strip()]

            # Format: username on one line, then "report_count\ttotal_score\trewards" on next
            # Skip header line containing "WhiteHats"
            i = 0
            while i < len(lines):
                if "WhiteHats" in lines[i] and "Report Count" in lines[i]:
                    i += 1
                    break
                i += 1

            rank = 0
            while i < len(lines) - 1:
                username = lines[i].strip()
                # Stop at pagination or footer
                if username.isdigit() and int(username) < 100:
                    # Could be pagination numbers at the bottom
                    if i + 1 < len(lines) and lines[i + 1].strip().isdigit():
                        break
                if "ALL RIGHTS" in username or "•••" in username:
                    break

                stats_line = lines[i + 1].strip()
                parts = stats_line.split("\t")
                if len(parts) >= 2:
                    rank += 1
                    score = None
                    extra = {}
                    try:
                        extra["report_count"] = int(parts[0].replace(",", ""))
                    except ValueError:
                        pass
                    try:
                        score = float(parts[1].replace(",", ""))
                    except ValueError:
                        pass
                    if len(parts) >= 3:
                        try:
                            extra["rewards_usdc"] = float(parts[2].replace(",", ""))
                        except ValueError:
                            pass

                    entries.append(
                        LeaderboardEntry(
                            username=username,
                            rank=rank,
                            score=score,
                            profile_url=f"{PROFILE_BASE}/{username}",
                            extra=extra,
                        )
                    )
                    i += 2

                    if len(entries) >= max_entries:
                        break
                else:
                    i += 1

            log.info("bugrap_leaderboard_scraped", entries=len(entries))

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

            bio = ""
            bio_match = re.search(r"(?:Bio|About|Description)\s*[:#]?\s*(.+?)(?:\n|$)", body, re.I)
            if bio_match:
                bio = bio_match.group(1).strip()

            # Extract severity breakdown
            for severity in ["Critical", "High", "Medium", "Low"]:
                sev_match = re.search(rf"{severity}\s*[:#]?\s*(\d+)", body, re.I)
                if sev_match:
                    raw_data[severity.lower()] = int(sev_match.group(1))

            external_links = await self._get_all_links(page, exclude_domain="bugrap.io")
            social_links = extract_social_links(body, external_links)

            profile = PlatformProfile(
                platform_name=self.platform_name,
                username=username,
                display_name=username,
                bio=bio,
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
