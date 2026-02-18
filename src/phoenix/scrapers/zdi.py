"""ZDI (Zero Day Initiative) scraper — Tier 2 (HTML parsing).

ZDI publishes advisories at zerodayinitiative.com/advisories/published/.
The page contains an HTML table with advisory data. ZDI tracks advisories,
not researcher leaderboards directly.
"""

import re
from datetime import datetime, UTC

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

BASE_URL = "https://www.zerodayinitiative.com"


@register_scraper("zdi")
class ZdiScraper(ApiScraper):
    """HTML-tier scraper for ZDI advisories."""

    platform_name = "zdi"

    def __init__(self) -> None:
        super().__init__()
        self._client.headers["Accept"] = "text/html,application/xhtml+xml,*/*"

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        """Parse the advisories table from the published advisories page.

        Each row has TDs: advisory_id, zdi_can, vendor, cve, cvss_score,
        published_date, updated_date, description_link.
        Returns advisory IDs as entries.
        """
        try:
            resp = await self._get(f"{BASE_URL}/advisories/published/")
            html = resp.text
        except Exception as e:
            log.warning("zdi_advisories_page_failed", error=str(e))
            return []

        entries: list[LeaderboardEntry] = []

        # Parse table rows for advisory data
        # Look for ZDI advisory ID pattern in table cells
        row_pattern = re.compile(
            r'<tr[^>]*>\s*'
            r'<td[^>]*>\s*(?:<a[^>]*>)?\s*(ZDI-\d{2}-\d+)\s*(?:</a>)?\s*</td>\s*'
            r'<td[^>]*>\s*(.*?)\s*</td>\s*'  # zdi_can
            r'<td[^>]*>\s*(.*?)\s*</td>\s*'  # vendor
            r'<td[^>]*>\s*(.*?)\s*</td>',     # cve
            re.DOTALL | re.IGNORECASE,
        )

        for i, match in enumerate(row_pattern.finditer(html)):
            if len(entries) >= max_entries:
                break

            advisory_id = match.group(1).strip()
            vendor = re.sub(r'<[^>]+>', '', match.group(3)).strip()
            cve = re.sub(r'<[^>]+>', '', match.group(4)).strip()

            entries.append(
                LeaderboardEntry(
                    username=advisory_id,
                    rank=i + 1,
                    score=None,
                    profile_url=f"{BASE_URL}/advisories/{advisory_id}/",
                    extra={
                        "vendor": vendor,
                        "cve": cve,
                    },
                )
            )

        # If the structured pattern didn't match, try a simpler approach
        if not entries:
            advisory_ids = re.findall(r'(ZDI-\d{2}-\d+)', html)
            seen: set[str] = set()
            for advisory_id in advisory_ids:
                if advisory_id in seen:
                    continue
                seen.add(advisory_id)
                if len(entries) >= max_entries:
                    break
                entries.append(
                    LeaderboardEntry(
                        username=advisory_id,
                        rank=len(entries) + 1,
                        score=None,
                        profile_url=f"{BASE_URL}/advisories/{advisory_id}/",
                    )
                )

        log.info("zdi_advisories_parsed", count=len(entries))
        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        """Fetch an individual advisory page by its ZDI ID."""
        try:
            resp = await self._get(f"{BASE_URL}/advisories/{username}/")
            html = resp.text
        except Exception as e:
            raise ValueError(f"ZDI advisory not found: {username} ({e})") from e

        # Extract advisory details from the page
        title_match = re.search(r'<h[12][^>]*>\s*(.+?)\s*</h', html, re.DOTALL | re.IGNORECASE)
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else username

        # Extract CVE
        cve_pattern = re.compile(r'(CVE-\d{4}-\d+)', re.IGNORECASE)
        cves = list(set(cve_pattern.findall(html)))

        # Extract CVSS score
        cvss_match = re.search(r'CVSS.*?(\d+\.?\d*)', html, re.IGNORECASE)
        cvss_score = float(cvss_match.group(1)) if cvss_match else None

        # Extract vendor
        vendor_match = re.search(r'(?:vendor|affected)[^<]*?:\s*([^<]+)', html, re.IGNORECASE)
        vendor = vendor_match.group(1).strip() if vendor_match else ""

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=title,
            bio=f"ZDI Advisory {username}",
            profile_url=f"{BASE_URL}/advisories/{username}/",
            social_links=[],
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=cvss_score,
            raw_data={
                "advisory_id": username,
                "title": title,
                "cves": cves,
                "vendor": vendor,
                "cvss_score": cvss_score,
            },
        )

        return profile, snapshot
