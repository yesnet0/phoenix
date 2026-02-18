"""Intigriti scraper — Tier 3 (Playwright, JS-rendered SPA)."""

from playwright.async_api import async_playwright, Browser, Page

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlatformScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.stealth import apply_stealth, random_ua, random_viewport
from phoenix.scrapers.utils.timing import jittered_delay

log = get_logger(__name__)

LEADERBOARD_URL = "https://app.intigriti.com/researcher/leaderboard"
PROFILE_BASE = "https://app.intigriti.com/researcher/profile"


@register_scraper("intigriti")
class IntigritiScraper(PlatformScraper):
    platform_name = "intigriti"

    def __init__(self) -> None:
        self._pw = None
        self._browser: Browser | None = None
        self._intercepted_api: list[dict] = []

    async def _get_browser(self) -> Browser:
        if self._browser is None:
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
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

        # Intercept API responses to capture underlying data
        async def handle_response(response):
            if "/api/" in response.url and response.status == 200:
                try:
                    body = await response.json()
                    self._intercepted_api.append({"url": response.url, "data": body})
                except Exception:
                    pass

        page.on("response", handle_response)
        return page

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []
        self._intercepted_api.clear()

        try:
            await page.goto(LEADERBOARD_URL, wait_until="networkidle", timeout=30000)
            await jittered_delay(2.0, 4.0)

            # First check intercepted API responses for structured data
            for intercepted in self._intercepted_api:
                if "leaderboard" in intercepted["url"].lower():
                    data = intercepted["data"]
                    items = data if isinstance(data, list) else data.get("records", data.get("items", data.get("data", [])))
                    if isinstance(items, list):
                        for i, item in enumerate(items[:max_entries]):
                            username = item.get("userName") or item.get("username") or item.get("name", "")
                            if username:
                                entries.append(
                                    LeaderboardEntry(
                                        username=username,
                                        rank=item.get("rank", i + 1),
                                        score=item.get("reputation") or item.get("points"),
                                        profile_url=f"{PROFILE_BASE}/{username}",
                                    )
                                )
                    if entries:
                        return entries

            # Fallback: DOM scraping
            rows = await page.query_selector_all(
                "table tbody tr, [class*='leaderboard'] [class*='row'], [class*='researcher']"
            )

            for i, row in enumerate(rows[:max_entries]):
                try:
                    link = await row.query_selector("a[href*='profile']")
                    if link:
                        href = await link.get_attribute("href") or ""
                        username = href.rstrip("/").split("/")[-1]
                    else:
                        text = (await row.inner_text()).strip()
                        username = text.split()[0] if text else ""

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
        self._intercepted_api.clear()

        try:
            profile_url = f"{PROFILE_BASE}/{username}"
            await page.goto(profile_url, wait_until="networkidle", timeout=30000)
            await jittered_delay(2.0, 4.0)

            display_name = ""
            bio = ""
            location = ""
            raw_data: dict = {}
            rank = None
            score = None

            # Check intercepted API for profile data
            for intercepted in self._intercepted_api:
                if "profile" in intercepted["url"].lower() or username.lower() in intercepted["url"].lower():
                    data = intercepted["data"]
                    if isinstance(data, dict):
                        display_name = data.get("name") or data.get("displayName", "")
                        bio = data.get("bio", "")
                        location = data.get("location", "")
                        rank = data.get("rank")
                        score = data.get("reputation") or data.get("points")
                        raw_data = data
                        break

            # Supplement with DOM scraping if API didn't provide enough
            if not display_name:
                for selector in ["h1", "[class*='name']", "[class*='username']"]:
                    el = await page.query_selector(selector)
                    if el:
                        display_name = (await el.inner_text()).strip()
                        break

            if not bio:
                for selector in ["[class*='bio']", "[class*='about']"]:
                    el = await page.query_selector(selector)
                    if el:
                        bio = (await el.inner_text()).strip()
                        break

            # Extract social links
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
                overall_score=score,
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
