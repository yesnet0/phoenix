"""Bugcrowd scraper — Tier 3 (Playwright, Cloudflare-protected SPA).

Leaderboard: table at /leaderboard with rows containing rank, username, points, submissions.
Profile: /h/{username} — SPA rendering with stats, achievements, priority percentiles.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://bugcrowd.com/leaderboard"
PROFILE_BASE = "https://bugcrowd.com/h"


@register_scraper("bugcrowd")
class BugcrowdScraper(PlaywrightScraper):
    platform_name = "bugcrowd"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="networkidle", timeout=30000)

            rows = await page.query_selector_all("table tbody tr")
            log.info("bugcrowd_rows_found", count=len(rows))

            for i, row in enumerate(rows[:max_entries]):
                try:
                    link = await row.query_selector('a[href*="/h/"]')
                    if not link:
                        continue

                    href = await link.get_attribute("href") or ""
                    username = href.rstrip("/").split("/")[-1]
                    if not username:
                        continue

                    cells = await row.query_selector_all("td")
                    cell_texts = []
                    for cell in cells:
                        text = (await cell.inner_text()).strip()
                        cell_texts.append(text)

                    rank = None
                    if cell_texts and cell_texts[0].isdigit():
                        rank = int(cell_texts[0])
                    else:
                        rank = i + 1

                    score = None
                    if len(cell_texts) >= 3:
                        try:
                            score = float(cell_texts[2].replace(",", ""))
                        except ValueError:
                            pass

                    entries.append(
                        LeaderboardEntry(
                            username=username,
                            rank=rank,
                            score=score,
                            profile_url=f"{PROFILE_BASE}/{username}",
                            extra={"submissions": cell_texts[3] if len(cell_texts) >= 4 else None},
                        )
                    )
                except Exception as e:
                    log.warning("bugcrowd_row_failed", index=i, error=str(e))

        finally:
            await page.context.close()

        return entries

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        page = await self._new_page()

        try:
            profile_url = f"{PROFILE_BASE}/{username}"
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            body = await self._get_body_text(page)

            raw_data: dict = {}
            rank = None
            score = None
            accuracy = None
            vuln_count = None

            points_match = re.search(r"All-time points\s*\n\s*(\d[\d,]*)", body)
            if points_match:
                score = float(points_match.group(1).replace(",", ""))
                raw_data["all_time_points"] = score

            rank_match = re.search(r"Current rank\s*\n\s*(\d+)", body)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            acc_match = re.search(r"Accuracy\s*\n\s*([\d.]+)%", body)
            if acc_match:
                accuracy = float(acc_match.group(1))
                raw_data["accuracy"] = accuracy

            vuln_match = re.search(r"Vulnerabilities\s*\n\s*(\d[\d,]*)", body)
            if vuln_match:
                vuln_count = int(vuln_match.group(1).replace(",", ""))
                raw_data["vulnerabilities"] = vuln_count

            for p in ["P1", "P2", "P3", "P4", "P5"]:
                p_match = re.search(rf"{p}\s*-\s*(\d+)", body)
                if p_match:
                    raw_data[f"{p.lower()}_percentile"] = int(p_match.group(1))

            programs_match = re.search(r"Total programs\s*(\d+)", body)
            if programs_match:
                raw_data["total_programs"] = int(programs_match.group(1))

            external_links = await self._get_all_links(page, exclude_domain="bugcrowd.com")
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
                finding_count=vuln_count,
                acceptance_rate=accuracy,
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()
