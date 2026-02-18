"""Huntr scraper — Tier 3 (Playwright, Next.js RSC).

Huntr is a security vulnerability bounty platform focused on open source.
It uses Next.js React Server Components with no traditional API or
__NEXT_DATA__. Playwright is required.

RSC hydration note: The leaderboard table renders skeleton rows immediately,
then hydrates each user's data via individual POST requests to /leaderboard.
Stealth UA/viewport settings break this hydration, so we use a plain browser
context for the leaderboard scrape. Each row takes ~1.5s to hydrate, so we
poll until enough rows are filled.
"""

import re

from playwright.async_api import Page

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://huntr.com/leaderboard"
PROFILE_BASE = "https://huntr.com/users"


@register_scraper("huntr")
class HuntrScraper(PlaywrightScraper):
    platform_name = "huntr"

    async def _new_plain_page(self) -> Page:
        """Create a page without stealth settings.

        Huntr's RSC hydration fails with custom UA/viewport stealth
        settings, so we use a plain browser context for reliability.
        """
        browser = await self._get_browser()
        context = await browser.new_context()
        page = await context.new_page()
        return page

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        # Use plain page -- stealth breaks RSC hydration on huntr
        page = await self._new_plain_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)

            # Wait for first td to be attached (RSC starts streaming)
            # Note: use state="attached" because headless mode may not
            # consider elements "visible" even when present in DOM
            try:
                await page.wait_for_selector("td", state="attached", timeout=20000)
            except Exception:
                log.warning("huntr_no_table_data", msg="No td elements appeared within 20s")
                return entries

            # Poll until enough rows have hydrated names (RSC loads lazily)
            target = min(max_entries, 25)
            for _ in range(15):
                await page.wait_for_timeout(2000)
                rows = await page.query_selector_all("tr")
                filled = 0
                for row in rows[1:]:  # skip header
                    tds = await row.query_selector_all("td")
                    if len(tds) >= 2:
                        name_text = await tds[1].inner_text()
                        if name_text.strip():
                            filled += 1
                if filled >= target:
                    break

            # Parse hydrated rows: [rank, "display_name\n@username", status, accuracy, xp]
            rows = await page.query_selector_all("tr")
            for row in rows[1:]:  # skip header
                tds = await row.query_selector_all("td")
                if len(tds) < 5:
                    continue

                rank_text = (await tds[0].inner_text()).strip()
                name_text = (await tds[1].inner_text()).strip()
                status_text = (await tds[2].inner_text()).strip()
                acc_text = (await tds[3].inner_text()).strip()
                xp_text = (await tds[4].inner_text()).strip()

                if not name_text or not rank_text.isdigit():
                    continue

                rank = int(rank_text)

                # Parse "display_name\n\n@username" or "display_name@username"
                username_match = re.search(r"@(\S+)", name_text)
                if not username_match:
                    continue
                username = username_match.group(1)
                display_name = re.split(r"\n|@", name_text)[0].strip()

                # Parse XP score
                score = None
                try:
                    score = float(xp_text.replace(",", ""))
                except ValueError:
                    pass

                extra = {}
                if status_text:
                    extra["status"] = status_text
                acc_match = re.match(r"(\d+)%", acc_text)
                if acc_match:
                    extra["accuracy"] = int(acc_match.group(1))
                if display_name and display_name != username:
                    extra["display_name"] = display_name

                entries.append(
                    LeaderboardEntry(
                        username=username,
                        rank=rank,
                        score=score,
                        profile_url=f"{PROFILE_BASE}/{username}",
                        extra=extra,
                    )
                )

                if len(entries) >= max_entries:
                    break

            log.info("huntr_leaderboard_parsed", count=len(entries))

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

            # Extract bounties/score
            bounty_match = re.search(r"(?:bounties?|score|points|rewards?)\s*\n?\s*\$?([\d,]+(?:\.\d+)?)", body, re.IGNORECASE)
            if bounty_match:
                score = float(bounty_match.group(1).replace(",", ""))
                raw_data["bounties"] = score

            # Extract rank
            rank_match = re.search(r"(?:rank|position)\s*\n?\s*#?(\d+)", body, re.IGNORECASE)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            # Extract disclosure/vulnerability count
            disc_match = re.search(r"(?:disclosures?|vulnerabilit|CVEs?|findings?)\s*\n?\s*(\d+)", body, re.IGNORECASE)
            if disc_match:
                finding_count = int(disc_match.group(1))
                raw_data["disclosures"] = finding_count

            external_links = await self._get_all_links(page, exclude_domain="huntr.com")
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
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()
