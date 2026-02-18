"""Open Bug Bounty scraper — Tier 2 (HTML parsing).

Open Bug Bounty is a non-profit coordinated vulnerability disclosure platform.
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

BASE_URL = "https://www.openbugbounty.org"


@register_scraper("openbugbounty")
class OpenBugBountyScraper(ApiScraper):
    """HTML-tier scraper using httpx + regex (no BeautifulSoup)."""

    platform_name = "openbugbounty"

    def __init__(self) -> None:
        super().__init__()
        # Override Accept header for HTML content
        self._client.headers["Accept"] = "text/html,application/xhtml+xml,*/*"

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        entries: list[LeaderboardEntry] = []
        page = 1

        while len(entries) < max_entries:
            try:
                resp = await self._get(
                    f"{BASE_URL}/researchers/top/",
                    params={"page": page},
                )
            except Exception:
                # Try alternative URL pattern
                try:
                    resp = await self._get(f"{BASE_URL}/researchers/page/{page}/")
                except Exception:
                    break

            html = resp.text

            # Pattern: look for researcher rows in HTML tables
            # Common pattern: <a href="/researcher/USERNAME">NAME</a> ... <td>SCORE</td>
            row_pattern = re.compile(
                r'<tr[^>]*>.*?'
                r'<a\s+href=["\']?/researcher/([^"\'>/]+)["\']?[^>]*>([^<]+)</a>'
                r'(.*?)</tr>',
                re.DOTALL | re.IGNORECASE,
            )

            found_any = False
            for match in row_pattern.finditer(html):
                username = match.group(1).strip()
                display_name = match.group(2).strip()
                row_rest = match.group(3)

                if not username:
                    continue

                # Extract numbers from remaining cells
                numbers = re.findall(r'<td[^>]*>\s*(\d[\d,]*)\s*</td>', row_rest)
                score = int(numbers[0].replace(",", "")) if numbers else None

                found_any = True
                entries.append(
                    LeaderboardEntry(
                        username=username,
                        rank=len(entries) + 1,
                        score=score,
                        profile_url=f"{BASE_URL}/researcher/{username}",
                        extra={"display_name": display_name},
                    )
                )
                if len(entries) >= max_entries:
                    break

            if not found_any:
                # Try alternative pattern: div-based layout
                div_pattern = re.compile(
                    r'href=["\']?/researcher/([^"\'>/]+)["\']?[^>]*>\s*'
                    r'(?:<[^>]+>)*\s*([^<]+)',
                    re.IGNORECASE,
                )
                for match in div_pattern.finditer(html):
                    username = match.group(1).strip()
                    if not username or username in ("top", "page"):
                        continue
                    entries.append(
                        LeaderboardEntry(
                            username=username,
                            rank=len(entries) + 1,
                            score=None,
                            profile_url=f"{BASE_URL}/researcher/{username}",
                        )
                    )
                    if len(entries) >= max_entries:
                        break

            if not found_any and not entries:
                break

            page += 1

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        resp = await self._get(f"{BASE_URL}/researcher/{username}")
        html = resp.text

        # Extract display name
        name_match = re.search(
            r'<h[1-3][^>]*>\s*(?:<[^>]+>)*\s*([^<]+)',
            html,
        )
        display_name = name_match.group(1).strip() if name_match else username

        # Extract bio/description
        bio_match = re.search(
            r'(?:bio|description|about)["\s:>]+([^<]{10,500})',
            html,
            re.IGNORECASE,
        )
        bio = bio_match.group(1).strip() if bio_match else ""

        # Extract total reports/bugs
        report_match = re.search(
            r'(?:total\s*(?:reports?|bugs?|vulnerabilit))[^<]*?(\d[\d,]*)',
            html,
            re.IGNORECASE,
        )
        finding_count = int(report_match.group(1).replace(",", "")) if report_match else None

        # Extract fixed count
        fixed_match = re.search(
            r'(?:fixed)[^<]*?(\d[\d,]*)',
            html,
            re.IGNORECASE,
        )
        fixed_count = int(fixed_match.group(1).replace(",", "")) if fixed_match else None

        # Extract all URLs from profile page
        all_urls = re.findall(r'href=["\']?(https?://[^"\'>\s]+)', html)
        social_links = extract_social_links(bio, all_urls)

        # Extract rank if present
        rank_match = re.search(r'(?:rank|position)[^<]*?#?(\d+)', html, re.IGNORECASE)
        global_rank = int(rank_match.group(1)) if rank_match else None

        # Extract score/points
        score_match = re.search(
            r'(?:score|points|reputation)[^<]*?(\d[\d,]*)',
            html,
            re.IGNORECASE,
        )
        score = float(score_match.group(1).replace(",", "")) if score_match else None

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=display_name,
            bio=bio,
            profile_url=f"{BASE_URL}/researcher/{username}",
            social_links=social_links,
        )

        raw_data: dict = {}
        if fixed_count is not None:
            raw_data["fixed_count"] = fixed_count

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=score,
            global_rank=global_rank,
            finding_count=finding_count,
            acceptance_rate=(fixed_count / finding_count) if finding_count and fixed_count else None,
            raw_data=raw_data,
        )

        return profile, snapshot
