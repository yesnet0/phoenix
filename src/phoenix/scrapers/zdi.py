"""ZDI (Zero Day Initiative) scraper — Tier 2 (HTML parsing).

Scrapes advisory detail pages from zerodayinitiative.com to extract
credited researchers. Groups advisories by researcher name and creates
one profile per unique researcher (skipping "Anonymous" credits).
"""

import re
from collections import defaultdict
from datetime import datetime, UTC

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.retry import scrape_retry
from phoenix.scrapers.utils.timing import jittered_delay

log = get_logger(__name__)

BASE_URL = "https://www.zerodayinitiative.com"

# Regex to extract researcher name from advisory detail page.
# Pattern: <td>CREDIT</td> followed by <td>RESEARCHER NAME<br /></td>
_CREDIT_RE = re.compile(
    r"<td>\s*CREDIT\s*</td>\s*<td>\s*(.*?)\s*(?:<br\s*/?>)?\s*</td>",
    re.DOTALL | re.IGNORECASE,
)

# Regex to extract CVE IDs from advisory pages
_CVE_RE = re.compile(r"(CVE-\d{4}-\d+)", re.IGNORECASE)


def _slugify(name: str) -> str:
    """Convert a researcher name to a URL-safe username slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)  # strip non-alphanum except spaces/hyphens
    slug = re.sub(r"[\s_]+", "-", slug)   # spaces/underscores → hyphens
    slug = re.sub(r"-{2,}", "-", slug)    # collapse multiple hyphens
    return slug.strip("-")


@register_scraper("zdi")
class ZdiScraper(ApiScraper):
    """HTML-tier scraper for ZDI credited researchers."""

    platform_name = "zdi"

    def __init__(self) -> None:
        super().__init__()
        self._client.headers["Accept"] = "text/html,application/xhtml+xml,*/*"
        # Cache populated during scrape_leaderboard, consumed by scrape_profile
        self._researcher_cache: dict[str, dict] = {}

    async def _fetch_advisory_credit(self, advisory_id: str) -> tuple[str, list[str]] | None:
        """Fetch a single advisory detail page and extract the credited researcher + CVEs.

        Returns (credit_text, [cve_ids]) or None on failure.
        """
        try:
            resp = await self._get(f"{BASE_URL}/advisories/{advisory_id}/")
            html = resp.text
        except Exception as e:
            log.debug("zdi_advisory_fetch_failed", advisory_id=advisory_id, error=str(e))
            return None

        credit_match = _CREDIT_RE.search(html)
        if not credit_match:
            log.debug("zdi_no_credit_found", advisory_id=advisory_id)
            return None

        credit_text = re.sub(r"<[^>]+>", "", credit_match.group(1)).strip()
        if not credit_text:
            return None

        cves = list(set(_CVE_RE.findall(html)))
        return credit_text, cves

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        """Scrape advisory listing, fetch detail pages for CREDIT, group by researcher.

        Returns one LeaderboardEntry per unique researcher (excluding Anonymous).
        """
        # Fetch the advisory listing page
        try:
            resp = await self._get(f"{BASE_URL}/advisories/published/")
            html = resp.text
        except Exception as e:
            log.warning("zdi_advisories_page_failed", error=str(e))
            return []

        # Extract unique advisory IDs from the listing
        all_ids = re.findall(r"(ZDI-\d{2}-\d+)", html)
        seen: set[str] = set()
        advisory_ids: list[str] = []
        for aid in all_ids:
            if aid not in seen:
                seen.add(aid)
                advisory_ids.append(aid)

        # Cap the number of advisories to scan
        max_advisories = max_entries * 3  # scan more advisories than entries to find enough researchers
        advisory_ids = advisory_ids[:max_advisories]

        log.info("zdi_advisory_ids_found", count=len(advisory_ids))

        # Fetch each advisory detail page and extract credited researchers
        # researcher_name -> {advisory_ids: [...], cves: [...]}
        researchers: dict[str, dict] = defaultdict(lambda: {"advisory_ids": [], "cves": []})

        for advisory_id in advisory_ids:
            result = await self._fetch_advisory_credit(advisory_id)
            if result is None:
                await jittered_delay(0.5, 1.5)
                continue

            credit_text, cves = result

            # Skip anonymous credits
            if credit_text.lower().strip() in ("anonymous", "anonymous."):
                await jittered_delay(0.5, 1.5)
                continue

            researchers[credit_text]["advisory_ids"].append(advisory_id)
            researchers[credit_text]["cves"].extend(cves)

            await jittered_delay(0.5, 1.5)

        log.info("zdi_researchers_found", count=len(researchers))

        # Build leaderboard entries sorted by advisory count (descending)
        sorted_researchers = sorted(researchers.items(), key=lambda x: len(x[1]["advisory_ids"]), reverse=True)

        entries: list[LeaderboardEntry] = []
        self._researcher_cache.clear()

        for rank, (name, data) in enumerate(sorted_researchers[:max_entries], start=1):
            slug = _slugify(name)
            if not slug:
                continue

            # Deduplicate CVEs
            data["cves"] = list(set(data["cves"]))

            # Cache for scrape_profile
            self._researcher_cache[slug] = {
                "display_name": name,
                "advisory_ids": data["advisory_ids"],
                "cves": data["cves"],
            }

            entries.append(
                LeaderboardEntry(
                    username=slug,
                    rank=rank,
                    score=float(len(data["advisory_ids"])),
                    profile_url=f"{BASE_URL}/advisories/{data['advisory_ids'][0]}/",
                    extra={
                        "advisory_count": len(data["advisory_ids"]),
                        "cves": data["cves"],
                    },
                )
            )

        log.info("zdi_leaderboard_built", entries=len(entries))
        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        """Build a researcher profile from cached advisory data.

        The username is a slugified researcher name populated during scrape_leaderboard.
        """
        cached = self._researcher_cache.get(username)
        if cached is None:
            raise ValueError(f"ZDI researcher not in cache: {username} (run scrape_leaderboard first)")

        display_name = cached["display_name"]
        advisory_ids = cached["advisory_ids"]
        cves = cached["cves"]
        advisory_count = len(advisory_ids)

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=display_name,
            bio=f"ZDI credited researcher — {advisory_count} advisor{'y' if advisory_count == 1 else 'ies'}",
            profile_url=f"{BASE_URL}/advisories/{advisory_ids[0]}/",
            social_links=[],
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            finding_count=advisory_count,
            raw_data={
                "researcher_name": display_name,
                "advisory_count": advisory_count,
                "advisory_ids": advisory_ids,
                "cves": cves,
            },
        )

        return profile, snapshot
