"""Platform and skill models."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ScraperTier(StrEnum):
    API = "api"
    HTML = "html"
    JS_RENDERED = "js_rendered"


class Platform(BaseModel):
    name: str  # "hackerone", "bugcrowd", "intigriti"
    display_name: str
    base_url: str
    scraper_tier: ScraperTier
    enabled: bool = True


class Skill(BaseModel):
    id: str = ""
    name: str
    category: str = ""


# Seed data for the 3 launch platforms
PLATFORMS: list[Platform] = [
    Platform(
        name="hackerone",
        display_name="HackerOne",
        base_url="https://hackerone.com",
        scraper_tier=ScraperTier.API,
    ),
    Platform(
        name="bugcrowd",
        display_name="Bugcrowd",
        base_url="https://bugcrowd.com",
        scraper_tier=ScraperTier.JS_RENDERED,
    ),
    Platform(
        name="intigriti",
        display_name="Intigriti",
        base_url="https://app.intigriti.com",
        scraper_tier=ScraperTier.JS_RENDERED,
    ),
]
