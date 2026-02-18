"""Scraper registry — maps platform names to scraper classes with auto-discovery."""

import importlib
import pkgutil

from phoenix.scrapers.base import PlatformScraper

_registry: dict[str, type[PlatformScraper]] = {}
_discovered = False


def register_scraper(platform_name: str):
    """Decorator to register a scraper class."""

    def decorator(cls: type[PlatformScraper]):
        cls.platform_name = platform_name
        _registry[platform_name] = cls
        return cls

    return decorator


def discover_scrapers() -> None:
    """Auto-discover all scraper modules in the phoenix.scrapers package."""
    global _discovered
    if _discovered:
        return

    import phoenix.scrapers as pkg

    for _, name, _ in pkgutil.iter_modules(pkg.__path__):
        if name in ("base", "registry") or name.startswith("_"):
            continue
        importlib.import_module(f"phoenix.scrapers.{name}")

    _discovered = True


def get_scraper(platform_name: str) -> PlatformScraper:
    """Instantiate a scraper by platform name."""
    discover_scrapers()
    cls = _registry.get(platform_name)
    if cls is None:
        raise ValueError(f"No scraper registered for platform: {platform_name}")
    return cls()


def list_scrapers() -> list[str]:
    discover_scrapers()
    return sorted(_registry.keys())
