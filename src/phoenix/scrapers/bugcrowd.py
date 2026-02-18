"""Bugcrowd scraper — Tier 3 (Playwright, Cloudflare-protected SPA)."""

from playwright.async_api import async_playwright, Browser, Page

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlatformScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.stealth import apply_stealth, random_ua, random_viewport
from phoenix.scrapers.utils.timing import jittered_delay

log = get_logger(__name__)

LEADERBOARD_URL = "https://bugcrowd.com/leaderboard"
PROFILE_BASE = "https://bugcrowd.com"


@register_scraper("bugcrowd")
class BugcrowdScraper(PlatformScraper):
    platform_name = "bugcrowd"

    def __init__(self) -> None:
        self._pw = None
        self._browser: Browser | None = None

    async def _get_browser(self) -> Browser:
        if self._browser is None:
            self._pw = await async_playwright().start()
            viewport = random_viewport()
            self._browser = await self._pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    f"--window-size={viewport['width']},{viewport['height']}",
                ],
            )
        return self._browser

    async def _new_page(self) -> Page:
        browser = await self._get_browser()
        viewport = random_viewport()
        context = await browser.new_context(
            viewport=viewport,
            user_agent=random_ua(),
            locale="en-US",
        )
        page = await context.new_page()
        await apply_stealth(page)
        return page

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_selector("[class*='leaderboard']", timeout=15000)

            # Extract leaderboard rows — selectors may need updating based on live page
            rows = await page.query_selector_all("table tbody tr, [class*='leaderboard-row'], [data-testid*='row']")

            if not rows:
                # Fallback: try to find any links that look like researcher profiles
                rows = await page.query_selector_all("a[href*='/researcher/'], a[href*='/user/']")

            for i, row in enumerate(rows[:max_entries]):
                try:
                    # Try to extract username from link href
                    link = await row.query_selector("a[href*='/']")
                    if link is None:
                        link = row if await row.get_attribute("href") else None

                    if link:
                        href = await link.get_attribute("href") or ""
                        username = href.rstrip("/").split("/")[-1]
                        text = await row.inner_text()
                    else:
                        text = await row.inner_text()
                        username = text.strip().split()[0] if text.strip() else ""

                    if username:
                        entries.append(
                            LeaderboardEntry(
                                username=username,
                                rank=i + 1,
                                profile_url=f"{PROFILE_BASE}/{username}",
                            )
                        )
                except Exception as e:
                    log.warning("leaderboard_row_failed", index=i, error=str(e))

        finally:
            await page.context.close()

        return entries

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        page = await self._new_page()

        try:
            profile_url = f"{PROFILE_BASE}/{username}"
            await page.goto(profile_url, wait_until="networkidle", timeout=30000)
            await jittered_delay(1.0, 3.0)

            # Extract profile data — selectors determined by live page structure
            display_name = ""
            bio = ""
            location = ""
            raw_data: dict = {}

            # Try common patterns for profile info
            for selector in ["h1", "[class*='display-name']", "[class*='username']", "[data-testid='name']"]:
                el = await page.query_selector(selector)
                if el:
                    display_name = (await el.inner_text()).strip()
                    break

            for selector in ["[class*='bio']", "[class*='about']", "[data-testid='bio']"]:
                el = await page.query_selector(selector)
                if el:
                    bio = (await el.inner_text()).strip()
                    break

            for selector in ["[class*='location']", "[data-testid='location']"]:
                el = await page.query_selector(selector)
                if el:
                    location = (await el.inner_text()).strip()
                    break

            # Extract any visible stats
            stat_els = await page.query_selector_all("[class*='stat'], [class*='metric'], [class*='score']")
            for el in stat_els:
                text = (await el.inner_text()).strip()
                if text:
                    raw_data[f"stat_{len(raw_data)}"] = text

            # Rank extraction
            rank = None
            for selector in ["[class*='rank']", "[data-testid='rank']"]:
                el = await page.query_selector(selector)
                if el:
                    rank_text = (await el.inner_text()).strip().replace("#", "").replace(",", "")
                    try:
                        rank = int(rank_text)
                    except ValueError:
                        pass
                    break

            # Extract social links from page
            all_links = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            social_links = extract_social_links(bio, all_links)

            profile = PlatformProfile(
                platform_name=self.platform_name,
                username=username,
                display_name=display_name,
                bio=bio,
                location=location,
                profile_url=profile_url,
                social_links=social_links,
            )

            snapshot = ProfileSnapshot(
                profile_id=profile.id,
                global_rank=rank,
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
