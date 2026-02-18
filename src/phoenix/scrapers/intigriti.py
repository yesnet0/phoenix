"""Intigriti scraper — Tier 3 (Playwright, JS-rendered SPA).

Leaderboard: app.intigriti.com/leaderboard — server-rendered table with rank, researcher, reputation, streak.
Profile: app.intigriti.com/profile/{username} — stats, skills, achievements, external accounts.
External accounts section provides cross-platform links (HackerOne, Bugcrowd, Twitter, etc.)
which are critical for identity resolution.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.timing import jittered_delay

log = get_logger(__name__)

LEADERBOARD_URL = "https://app.intigriti.com/leaderboard"
PROFILE_BASE = "https://app.intigriti.com/profile"


@register_scraper("intigriti")
class IntigritiScraper(PlaywrightScraper):
    platform_name = "intigriti"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            await self._dismiss_cookies(page)

            # Click "Show more" to load all entries
            for _ in range(10):
                try:
                    show_more = await page.query_selector("button:has-text('Show more')")
                    if show_more and await show_more.is_visible():
                        await show_more.click()
                        await page.wait_for_timeout(2000)
                    else:
                        break
                except Exception:
                    break

            body = await page.inner_text("body")

            lines = body.split("\n")
            lines = [l.strip() for l in lines if l.strip()]

            start_idx = None
            for i, line in enumerate(lines):
                if line == "STREAK":
                    start_idx = i + 1
                    break

            if start_idx:
                i = start_idx
                while i < len(lines) and len(entries) < max_entries:
                    if lines[i].isdigit():
                        rank = int(lines[i])
                        if i + 2 < len(lines):
                            username = lines[i + 1]
                            pts_match = re.match(r"(\d+)pts", lines[i + 2])
                            score = float(pts_match.group(1)) if pts_match else None
                            entries.append(
                                LeaderboardEntry(
                                    username=username,
                                    rank=rank,
                                    score=score,
                                    profile_url=f"{PROFILE_BASE}/{username}",
                                )
                            )
                            i += 4
                            continue
                    i += 1

            log.info("intigriti_leaderboard_scraped", entries=len(entries))

        finally:
            await page.context.close()

        return entries

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        page = await self._new_page()

        try:
            profile_url = f"{PROFILE_BASE}/{username}"
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            await self._dismiss_cookies(page)

            body = await page.inner_text("body")
            raw_data: dict = {}

            # Location — appears right after username
            location = ""
            lines = body.split("\n")
            lines = [l.strip() for l in lines if l.strip()]
            for i, line in enumerate(lines):
                if line == username and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if next_line not in ("REP. 90 DAYS", "REP. ALL TIME") and "pts" not in next_line:
                        location = next_line
                    break

            rep_90 = None
            rep_all = None
            rank = None
            accepted = None
            valid_pct = None
            total = None

            for stat_name, stat_key in [
                ("REP. 90 DAYS", "rep_90_days"),
                ("REP. ALL TIME", "rep_all_time"),
                ("RANK", "rank"),
                ("ACCEPTED", "accepted"),
                ("VALID", "valid"),
                ("TOTAL", "total"),
            ]:
                match = re.search(rf"{re.escape(stat_name)}\s*\n\s*([\d,.]+)(?:pts|%)?", body)
                if match:
                    val = match.group(1).replace(",", "")
                    raw_data[stat_key] = val

            if raw_data.get("rep_90_days"):
                rep_90 = float(raw_data["rep_90_days"])
            if raw_data.get("rep_all_time"):
                rep_all = float(raw_data["rep_all_time"])
            if raw_data.get("rank"):
                rank = int(raw_data["rank"])
            if raw_data.get("accepted"):
                accepted = int(raw_data["accepted"])
            if raw_data.get("valid"):
                valid_pct = float(raw_data["valid"])
            if raw_data.get("total"):
                total = int(raw_data["total"])

            skills: list[str] = []
            skill_section = re.search(r"Skills\n(.*?)(?:Industries|Achievements|Activity|$)", body, re.DOTALL)
            if skill_section:
                for line in skill_section.group(1).split("\n"):
                    line = line.strip()
                    if line and line not in ("Show all", "Show all "):
                        skills.append(line)

            external_links = await self._get_all_links(page, exclude_domain="intigriti")
            external_links = [l for l in external_links if "cookieyes" not in l and "google" not in l]
            social_links = extract_social_links(body, external_links)

            profile = PlatformProfile(
                platform_name=self.platform_name,
                username=username,
                display_name=username,
                location=location,
                profile_url=profile_url,
                social_links=social_links,
                skill_tags=skills,
            )

            snapshot = ProfileSnapshot(
                profile_id=profile.id,
                overall_score=rep_all,
                global_rank=rank,
                finding_count=accepted,
                acceptance_rate=valid_pct,
                raw_data={
                    **raw_data,
                    "rep_90_days_score": rep_90,
                    "total_submissions": total,
                },
            )

            return profile, snapshot

        finally:
            await page.context.close()
