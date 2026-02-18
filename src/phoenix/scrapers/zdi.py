"""ZDI (Zero Day Initiative) scraper — Tier 2 (HTML parsing).

ZDI publishes advisories and tracks researchers by their contributions.
No public API — scrape HTML with httpx and parse with regex.
"""

import re
from datetime import datetime, UTC

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

BASE_URL = "https://www.zerodayinitiative.com"


@register_scraper("zdi")
class ZdiScraper(ApiScraper):
    """HTML-tier scraper for ZDI advisories and researcher rankings."""

    platform_name = "zdi"

    def __init__(self) -> None:
        super().__init__()
        self._client.headers["Accept"] = "text/html,application/xhtml+xml,*/*"

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        """Scrape the ZDI researcher rankings from published advisories.

        ZDI does not have a traditional leaderboard. We aggregate researcher
        names from the advisories listing and rank by advisory count.
        """
        researcher_counts: dict[str, int] = {}
        entries: list[LeaderboardEntry] = []

        # Try the researcher/ranking page first
        ranking_urls = [
            f"{BASE_URL}/advisories/published/",
            f"{BASE_URL}/blog/published-advisories/",
        ]

        for url in ranking_urls:
            try:
                resp = await self._get(url)
                html = resp.text
                break
            except Exception:
                html = ""
                continue

        if not html:
            log.warning("zdi_no_advisory_page")
            return []

        # Extract researcher names from advisory entries
        # Common patterns: "Reported by: Name" or "Credit: Name" or researcher name in table
        credit_patterns = [
            re.compile(
                r'(?:reported\s+by|credit(?:ed)?(?:\s+to)?|discovered\s+by|researcher)\s*:?\s*'
                r'(?:<[^>]+>)*\s*([^<\n]{2,80})',
                re.IGNORECASE,
            ),
            re.compile(
                r'class=["\']?(?:researcher|credit|reporter)["\']?[^>]*>\s*([^<]+)',
                re.IGNORECASE,
            ),
        ]

        for pattern in credit_patterns:
            for match in pattern.finditer(html):
                name = match.group(1).strip().rstrip(",.")
                if name and len(name) > 1 and not name.startswith("http"):
                    researcher_counts[name] = researcher_counts.get(name, 0) + 1

        # Also try to find a dedicated ranking table
        table_pattern = re.compile(
            r'<tr[^>]*>.*?<td[^>]*>\s*(\d+)\s*</td>\s*'
            r'<td[^>]*>\s*(?:<[^>]+>)*\s*([^<]+)',
            re.DOTALL | re.IGNORECASE,
        )
        for match in table_pattern.finditer(html):
            rank_str = match.group(1).strip()
            name = match.group(2).strip()
            if name and name.lower() not in ("rank", "name", "researcher"):
                try:
                    researcher_counts[name] = max(
                        researcher_counts.get(name, 0),
                        int(rank_str),
                    )
                except ValueError:
                    pass

        # Sort by advisory count descending
        sorted_researchers = sorted(
            researcher_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        for i, (name, count) in enumerate(sorted_researchers[:max_entries]):
            # Create a URL-safe slug
            slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower()).strip('-')
            entries.append(
                LeaderboardEntry(
                    username=name,
                    rank=i + 1,
                    score=float(count),
                    profile_url=f"{BASE_URL}/advisories/published/?researcher={slug}",
                    extra={"advisory_count": count},
                )
            )

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        """Scrape ZDI advisory data for a specific researcher.

        Since ZDI does not have profile pages, we search advisories by
        researcher name and aggregate the data.
        """
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', username.lower()).strip('-')

        # Try to fetch advisories filtered by researcher
        html = ""
        search_urls = [
            f"{BASE_URL}/advisories/published/?researcher={slug}",
            f"{BASE_URL}/advisories/published/?q={slug}",
        ]

        for url in search_urls:
            try:
                resp = await self._get(url)
                html = resp.text
                if username.lower() in html.lower():
                    break
            except Exception:
                continue

        if not html:
            raise ValueError(f"ZDI researcher not found: {username}")

        # Count advisories
        advisory_pattern = re.compile(r'ZDI-\d{2}-\d+', re.IGNORECASE)
        advisories = list(set(advisory_pattern.findall(html)))
        advisory_count = len(advisories)

        # Extract severity/type information
        critical_pattern = re.compile(r'(?:critical|severity:\s*critical)', re.IGNORECASE)
        high_pattern = re.compile(r'(?:high|severity:\s*high)', re.IGNORECASE)

        critical_count = len(critical_pattern.findall(html))
        high_count = len(high_pattern.findall(html))

        # Extract any linked URLs
        all_urls = re.findall(r'href=["\']?(https?://[^"\'>\s]+)', html)
        social_links = extract_social_links("", all_urls)

        # Try to get CVE IDs associated with this researcher
        cve_pattern = re.compile(r'CVE-\d{4}-\d+', re.IGNORECASE)
        cves = list(set(cve_pattern.findall(html)))

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=username,
            bio=f"ZDI researcher with {advisory_count} published advisories",
            profile_url=f"{BASE_URL}/advisories/published/?researcher={slug}",
            social_links=social_links,
            badges=[f"{advisory_count} advisories"],
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=float(advisory_count),
            finding_count=advisory_count,
            critical_count=critical_count if critical_count else None,
            high_count=high_count if high_count else None,
            raw_data={
                "advisory_ids": advisories[:50],  # Cap stored IDs
                "cve_ids": cves[:50],
                "advisory_count": advisory_count,
                "cve_count": len(cves),
            },
        )

        return profile, snapshot
