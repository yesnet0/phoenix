"""BugBase scraper — Tier 3 (Playwright, Next.js SPA).

Leaderboard: https://bugbase.in/leaderboard
Profile: https://bugbase.in/dashboard/profile/{username}

Body text format:
- Top 3: expanded cards with label/value pairs on separate lines
  username, "Global Rank", rank, "Country", CC, "Success rate", N%, "Reputation", score
- 4+: compact table rows
  "Global Rank\tUsername\tRepuation\tSuccess Rate\tCountry" header, then
  rank, username, "score\trate%\tCC" per entry
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://bugbase.in/leaderboard"
PROFILE_BASE = "https://bugbase.in/dashboard/profile"


@register_scraper("bugbase")
class BugbaseScraper(PlaywrightScraper):
    platform_name = "bugbase"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page, wait_ms=8000)

            lines = [l.strip() for l in body.split("\n") if l.strip()]
            i = 0

            # Skip header lines until we hit the first username
            while i < len(lines):
                if lines[i] == "Global Leaderboard" or lines[i].startswith("Check out"):
                    i += 1
                    continue
                if lines[i] == "Global":
                    i += 1
                    continue
                break

            # Parse top-3 expanded cards: username, "Global Rank", N, "Country", CC, "Success rate", N%, "Reputation", score
            while i < len(lines) and len(entries) < min(3, max_entries):
                username = lines[i]
                # Verify next line is "Global Rank"
                if i + 4 < len(lines) and lines[i + 1] == "Global Rank":
                    rank = int(lines[i + 2])
                    # Find Reputation value
                    score = None
                    success_rate = None
                    country = None
                    j = i + 3
                    while j < len(lines) and j < i + 10:
                        if lines[j] == "Country" and j + 1 < len(lines):
                            country = lines[j + 1]
                        if lines[j] == "Success rate" and j + 1 < len(lines):
                            rate_match = re.match(r"(\d+)%", lines[j + 1])
                            if rate_match:
                                success_rate = float(rate_match.group(1))
                        if lines[j] == "Reputation" and j + 1 < len(lines):
                            try:
                                score = float(lines[j + 1])
                            except ValueError:
                                pass
                            i = j + 2
                            break
                        j += 1
                    else:
                        i = j

                    entries.append(
                        LeaderboardEntry(
                            username=username,
                            rank=rank,
                            score=score,
                            profile_url=f"{PROFILE_BASE}/{username}",
                            extra={
                                k: v for k, v in {
                                    "country": country,
                                    "success_rate": success_rate,
                                }.items() if v is not None
                            },
                        )
                    )
                else:
                    break

            # Skip table header line
            while i < len(lines):
                if "Global Rank" in lines[i] and "Username" in lines[i]:
                    i += 1
                    break
                i += 1

            # Parse compact rows: rank line, username line, "score\trate%\tCC" line
            while i + 2 < len(lines) and len(entries) < max_entries:
                rank_line = lines[i]
                if not rank_line.isdigit():
                    break
                rank = int(rank_line)
                username = lines[i + 1]
                stats_line = lines[i + 2]
                parts = stats_line.split("\t")

                score = None
                success_rate = None
                country = None
                if parts:
                    try:
                        score = float(parts[0].replace(",", ""))
                    except ValueError:
                        pass
                if len(parts) >= 2:
                    rate_match = re.match(r"(\d+)%", parts[1])
                    if rate_match:
                        success_rate = float(rate_match.group(1))
                if len(parts) >= 3:
                    country = parts[2].strip()

                entries.append(
                    LeaderboardEntry(
                        username=username,
                        rank=rank,
                        score=score,
                        profile_url=f"{PROFILE_BASE}/{username}",
                        extra={
                            k: v for k, v in {
                                "country": country,
                                "success_rate": success_rate,
                            }.items() if v is not None
                        },
                    )
                )
                i += 3

            log.info("bugbase_leaderboard_scraped", entries=len(entries))

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

            bugs_match = re.search(r"(?:Bugs?\s*(?:Found|Reported|Submitted))\s*[:#]?\s*(\d+)", body, re.I)
            if bugs_match:
                finding_count = int(bugs_match.group(1))
                raw_data["bugs_found"] = finding_count

            acc_match = re.search(r"(?:Acceptance|Valid)\s*(?:Rate)?\s*[:#]?\s*([\d.]+)\s*%", body, re.I)
            if acc_match:
                acceptance_rate = float(acc_match.group(1))
                raw_data["acceptance_rate"] = acceptance_rate

            display_name = username
            name_match = re.search(r"([A-Z][a-z]+ [A-Z][a-z]+)", body)
            if name_match:
                display_name = name_match.group(1)

            bio = ""
            bio_match = re.search(r"(?:Bio|About)\s*[:#]?\s*(.+?)(?:\n|$)", body, re.I)
            if bio_match:
                bio = bio_match.group(1).strip()

            external_links = await self._get_all_links(page, exclude_domain="bugbase.in")
            social_links = extract_social_links(body, external_links)

            profile = PlatformProfile(
                platform_name=self.platform_name,
                username=username,
                display_name=display_name,
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
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()
