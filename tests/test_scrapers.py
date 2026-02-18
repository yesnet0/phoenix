"""Test scraper registry and framework."""

import pytest

from phoenix.scrapers.base import LeaderboardEntry, PlatformScraper
from phoenix.scrapers.registry import _registry, get_scraper, list_scrapers, register_scraper


def test_list_scrapers_has_all_three():
    # Import app to trigger registration
    from phoenix.api.app import app  # noqa: F401

    scrapers = list_scrapers()
    assert "hackerone" in scrapers
    assert "bugcrowd" in scrapers
    assert "intigriti" in scrapers


def test_get_scraper_returns_instance():
    from phoenix.api.app import app  # noqa: F401

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
