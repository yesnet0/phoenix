"""Abstract base scraper and common data types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx
from playwright.async_api import async_playwright, Browser, Page

from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.utils.stealth import apply_stealth, random_ua, random_viewport


@dataclass
class LeaderboardEntry:
    """Minimal entry from a leaderboard page."""

    username: str
    rank: int | None = None
    score: float | None = None
    profile_url: str = ""
    extra: dict = field(default_factory=dict)


class PlatformScraper(ABC):
    """Abstract base for all platform scrapers."""

    platform_name: str = ""

    @abstractmethod
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        """Scrape the platform leaderboard, returning ranked entries."""
        ...

    @abstractmethod
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        """Scrape a single researcher profile. Returns profile + current snapshot."""
        ...

    async def scrape_full(self, max_profiles: int = 50) -> list[tuple[PlatformProfile, ProfileSnapshot]]:
        """Orchestrate: leaderboard → profile loop with per-profile error handling."""
        from phoenix.core.logging import get_logger
        from phoenix.scrapers.utils.timing import jittered_delay

        log = get_logger(f"scraper.{self.platform_name}")
        results: list[tuple[PlatformProfile, ProfileSnapshot]] = []

        entries = await self.scrape_leaderboard(max_entries=max_profiles)
        log.info("leaderboard_scraped", platform=self.platform_name, entries=len(entries))

        for entry in entries[:max_profiles]:
            try:
                profile, snapshot = await self.scrape_profile(entry.username)
                results.append((profile, snapshot))
                log.info("profile_scraped", username=entry.username)
            except Exception as e:
                log.error("profile_failed", username=entry.username, error=str(e))
            await jittered_delay()

        return results

    async def close(self) -> None:
        """Clean up resources (override if needed)."""
        pass


class ApiScraper(PlatformScraper):
    """Base class for API-based (Tier 1) scrapers using httpx."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": random_ua(),
                "Accept": "application/json",
            },
            timeout=30.0,
            follow_redirects=True,
        )

    async def _get(self, url: str, **kwargs) -> httpx.Response:
        resp = await self._client.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    async def _post(self, url: str, **kwargs) -> httpx.Response:
        resp = await self._client.post(url, **kwargs)
        resp.raise_for_status()
        return resp

    async def close(self) -> None:
        await self._client.aclose()


class PlaywrightScraper(PlatformScraper):
    """Base class for Playwright-based (Tier 3) scrapers."""

    def __init__(self) -> None:
        self._pw = None
        self._browser: Browser | None = None

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
        return page

    async def _dismiss_cookies(self, page: Page) -> None:
        """Try to dismiss common cookie consent banners."""
        for selector in [
            "button:has-text('Accept All')",
            "button:has-text('Accept all')",
            "button:has-text('Accept')",
            "button:has-text('I agree')",
            "button:has-text('Got it')",
            "button:has-text('OK')",
        ]:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(1000)
                    return
            except Exception:
                continue

    async def _get_body_text(self, page: Page, wait_ms: int = 5000) -> str:
        """Wait for SPA rendering then extract body text."""
        await page.wait_for_timeout(wait_ms)
        return await page.inner_text("body")

    async def _get_all_links(self, page: Page, exclude_domain: str = "") -> list[str]:
        """Extract all external links from page."""
        all_links = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        if exclude_domain:
            return [l for l in all_links if l.startswith("http") and exclude_domain not in l]
        return [l for l in all_links if l.startswith("http")]

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
