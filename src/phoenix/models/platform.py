"""Platform and skill models."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ScraperTier(StrEnum):
    API = "api"
    HTML = "html"
    JS_RENDERED = "js_rendered"


class Platform(BaseModel):
    name: str
    display_name: str
    base_url: str
    scraper_tier: ScraperTier
    enabled: bool = True


class Skill(BaseModel):
    id: str = ""
    name: str
    category: str = ""


# Seed data for all 35 platforms
PLATFORMS: list[Platform] = [
    # --- M1 platforms (3) ---
    Platform(name="hackerone", display_name="HackerOne", base_url="https://hackerone.com", scraper_tier=ScraperTier.API),
    Platform(name="bugcrowd", display_name="Bugcrowd", base_url="https://bugcrowd.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="intigriti", display_name="Intigriti", base_url="https://app.intigriti.com", scraper_tier=ScraperTier.JS_RENDERED),
    # --- Batch 1: API-based (12) ---
    Platform(name="yeswehack", display_name="YesWeHack", base_url="https://yeswehack.com", scraper_tier=ScraperTier.API),
    Platform(name="immunefi", display_name="Immunefi", base_url="https://immunefi.com", scraper_tier=ScraperTier.API),
    Platform(name="hackenproof", display_name="HackenProof", base_url="https://hackenproof.com", scraper_tier=ScraperTier.API),
    Platform(name="huntr", display_name="Huntr", base_url="https://huntr.dev", scraper_tier=ScraperTier.API),
    Platform(name="code4rena", display_name="Code4rena", base_url="https://code4rena.com", scraper_tier=ScraperTier.API),
    Platform(name="sherlock", display_name="Sherlock", base_url="https://app.sherlock.xyz", scraper_tier=ScraperTier.API),
    Platform(name="codehawks", display_name="CodeHawks", base_url="https://codehawks.cyfrin.io", scraper_tier=ScraperTier.API),
    Platform(name="patchstack", display_name="Patchstack", base_url="https://patchstack.com", scraper_tier=ScraperTier.API),
    Platform(name="openbugbounty", display_name="Open Bug Bounty", base_url="https://openbugbounty.org", scraper_tier=ScraperTier.HTML),
    Platform(name="hatsfinance", display_name="Hats Finance", base_url="https://app.hats.finance", scraper_tier=ScraperTier.API),
    Platform(name="zdi", display_name="Zero Day Initiative", base_url="https://zerodayinitiative.com", scraper_tier=ScraperTier.HTML),
    Platform(name="topcoder", display_name="Topcoder", base_url="https://topcoder.com", scraper_tier=ScraperTier.API),
    # --- Batch 2: Playwright SPA (20) ---
    Platform(name="bugbase", display_name="Bugbase", base_url="https://bugbase.in", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="bugbounter", display_name="BugBounter", base_url="https://app.bugbounter.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="bugbountysa", display_name="bugbounty.sa", base_url="https://bugbounty.sa", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="bugrap", display_name="BugRap", base_url="https://bugrap.io", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="certik", display_name="CertiK", base_url="https://skynet.certik.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="cyberarmy", display_name="Cyber Army ID", base_url="https://cyberarmy.id", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="epicbounties", display_name="EpicBounties", base_url="https://app.epicbounties.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="hackrate", display_name="Hackrate", base_url="https://hckrt.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="hacktify", display_name="HACKTIFY", base_url="https://hacktify.eu", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="huntbug", display_name="HuntBug", base_url="https://huntbug.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="safehats", display_name="Safehats", base_url="https://app.safehats.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="safevuln", display_name="Safevuln", base_url="https://safevuln.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="standoff365", display_name="Standoff 365", base_url="https://bugbounty.standoff365.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="teklabspace", display_name="Teklabspace", base_url="https://app.teklabspace.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="vulnscope", display_name="Vulnscope", base_url="https://vulnscope.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="whitehub", display_name="WhiteHub", base_url="https://whitehub.net", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="bughunt", display_name="Bug Hunt", base_url="https://bughunt.com.br", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="comolho", display_name="Com Olho", base_url="https://cyber.comolho.com", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="auditone", display_name="AuditOne", base_url="https://auditone.io", scraper_tier=ScraperTier.JS_RENDERED),
    Platform(name="vulbox", display_name="Vulbox", base_url="https://vulbox.com", scraper_tier=ScraperTier.JS_RENDERED),
]
