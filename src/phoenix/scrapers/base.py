"""Abstract base scraper and common data types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from phoenix.models.researcher import PlatformProfile, ProfileSnapshot


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
