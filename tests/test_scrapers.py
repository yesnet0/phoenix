"""Test scraper registry and framework."""

import pytest

from phoenix.models.platform import PLATFORMS
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry, PlaywrightScraper, PlatformScraper
from phoenix.scrapers.registry import _registry, discover_scrapers, get_scraper, list_scrapers, register_scraper


def test_list_scrapers_has_all_three():
    discover_scrapers()
    scrapers = list_scrapers()
    assert "hackerone" in scrapers
    assert "bugcrowd" in scrapers
    assert "intigriti" in scrapers


def test_get_scraper_returns_instance():
    discover_scrapers()
    scraper = get_scraper("hackerone")
    assert isinstance(scraper, PlatformScraper)
    assert scraper.platform_name == "hackerone"


def test_get_scraper_unknown_raises():
    with pytest.raises(ValueError, match="No scraper registered"):
        get_scraper("nonexistent_platform")


def test_leaderboard_entry_defaults():
    entry = LeaderboardEntry(username="alice", rank=1)
    assert entry.username == "alice"
    assert entry.rank == 1
    assert entry.score is None
    assert entry.extra == {}


def test_register_scraper_decorator():
    """Verify the decorator sets platform_name and registers the class."""

    @register_scraper("test_platform")
    class TestScraper(PlatformScraper):
        async def scrape_leaderboard(self, max_entries=100):
            return []

        async def scrape_profile(self, username):
            raise NotImplementedError

    assert TestScraper.platform_name == "test_platform"
    assert "test_platform" in _registry

    # Cleanup
    del _registry["test_platform"]


def test_all_35_scrapers_registered():
    """Verify all 35 platforms from the seed data have registered scrapers."""
    discover_scrapers()
    scrapers = set(list_scrapers())
    platform_names = {p.name for p in PLATFORMS}
    assert platform_names == scrapers, f"Missing scrapers: {platform_names - scrapers}, Extra scrapers: {scrapers - platform_names}"


def test_hackerone_is_api_scraper():
    discover_scrapers()
    scraper = get_scraper("hackerone")
    assert isinstance(scraper, ApiScraper)


def test_bugcrowd_is_playwright_scraper():
    discover_scrapers()
    scraper = get_scraper("bugcrowd")
    assert isinstance(scraper, PlaywrightScraper)


def test_intigriti_is_playwright_scraper():
    discover_scrapers()
    scraper = get_scraper("intigriti")
    assert isinstance(scraper, PlaywrightScraper)


def test_auto_discovery_is_idempotent():
    """Calling discover_scrapers multiple times should not duplicate registrations."""
    discover_scrapers()
    count1 = len(list_scrapers())
    discover_scrapers()
    count2 = len(list_scrapers())
    assert count1 == count2
