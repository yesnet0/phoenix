"""Scraper registry — maps platform names to scraper classes."""

from phoenix.scrapers.base import PlatformScraper

_registry: dict[str, type[PlatformScraper]] = {}


def register_scraper(platform_name: str):
    """Decorator to register a scraper class."""

    def decorator(cls: type[PlatformScraper]):
        cls.platform_name = platform_name
        _registry[platform_name] = cls
        return cls

    return decorator


def get_scraper(platform_name: str) -> PlatformScraper:
    """Instantiate a scraper by platform name."""
    cls = _registry.get(platform_name)
    if cls is None:
        raise ValueError(f"No scraper registered for platform: {platform_name}")
    return cls()


def list_scrapers() -> list[str]:
    return list(_registry.keys())
