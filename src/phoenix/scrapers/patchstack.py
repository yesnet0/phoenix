"""Patchstack scraper — Tier 1 (REST API).

Patchstack is a WordPress vulnerability disclosure platform with
a researcher leaderboard.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

BASE_URL = "https://patchstack.com"


@register_scraper("patchstack")
class PatchstackScraper(ApiScraper):
    platform_name = "patchstack"

    async def _fetch_leaderboard_data(self, max_entries: int) -> list[dict]:
        """Try API endpoints, then fall back to HTML/Next.js extraction."""
        api_paths = [
            f"{BASE_URL}/api/leaderboard",
            f"{BASE_URL}/api/v1/leaderboard",
            f"{BASE_URL}/api/researchers/leaderboard",
            f"{BASE_URL}/database/api/leaderboard",
        ]

        for path in api_paths:
            try:
                resp = await self._get(path, params={"limit": max_entries})
                data = resp.json()
                if isinstance(data, list):
                    return data
                for key in ("data", "results", "leaderboard", "researchers"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
            except Exception:
                continue

        # Fallback: try Next.js _next/data
        try:
            resp = await self._get(f"{BASE_URL}/database/leaderboard")
            html = resp.text
            build_match = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
            if build_match:
                build_id = build_match.group(1)
                resp = await self._get(
                    f"{BASE_URL}/_next/data/{build_id}/database/leaderboard.json",
                )
                page_props = resp.json().get("pageProps", {})
                for key in ("leaderboard", "researchers", "data"):
                    if key in page_props and isinstance(page_props[key], list):
                        return page_props[key]
        except Exception:
            pass

        # Last resort: parse HTML table
        try:
            resp = await self._get(f"{BASE_URL}/database/leaderboard")
            html = resp.text
            rows = re.findall(
                r'<tr[^>]*>.*?</tr>',
                html,
                re.DOTALL,
            )
            items = []
            for row in rows:
                name_match = re.search(r'<td[^>]*>\s*(?:<[^>]+>)*\s*([^<]+)', row)
                if name_match:
                    name = name_match.group(1).strip()
                    if name and name.lower() not in ("name", "researcher", "rank"):
                        nums = re.findall(r'>(\d+)</', row)
                        items.append({
                            "name": name,
                            "score": int(nums[0]) if nums else 0,
                        })
            return items
        except Exception:
            pass

        return []

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        items = await self._fetch_leaderboard_data(max_entries)
        entries: list[LeaderboardEntry] = []

        for i, item in enumerate(items[:max_entries]):
            username = (
                item.get("username")
                or item.get("handle")
                or item.get("name")
                or item.get("researcher", "")
            )
            if not username:
                continue
            # Normalize username for URL (spaces to hyphens, lowercase)
            url_slug = re.sub(r'\s+', '-', username.lower())

            entries.append(
                LeaderboardEntry(
                    username=username,
                    rank=item.get("rank", i + 1),
                    score=item.get("score", item.get("points", item.get("vulnerabilities"))),
                    profile_url=f"{BASE_URL}/database/researcher/{url_slug}",
                    extra={
                        k: item[k]
                        for k in ("vulnerabilities", "cves", "plugins_reported")
                        if k in item
                    },
                )
            )

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        user: dict = {}
        url_slug = re.sub(r'\s+', '-', username.lower())

        profile_paths = [
            f"{BASE_URL}/api/researchers/{url_slug}",
            f"{BASE_URL}/api/v1/researchers/{url_slug}",
            f"{BASE_URL}/database/api/researcher/{url_slug}",
        ]

        for path in profile_paths:
            try:
                resp = await self._get(path)
                data = resp.json()
                user = data.get("data", data) if isinstance(data, dict) else {}
                if user.get("username") or user.get("name"):
                    break
                user = {}
            except Exception:
                continue

        if not user:
            raise ValueError(f"Patchstack profile not found: {username}")

        bio = user.get("bio", "") or ""
        urls = [user[k] for k in ("website", "twitter", "github") if user.get(k)]
        social_links = extract_social_links(bio, urls)

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=user.get("name", user.get("display_name", username)),
            bio=bio,
            location=user.get("location", ""),
            profile_url=f"{BASE_URL}/database/researcher/{url_slug}",
            social_links=social_links,
            badges=[str(b) for b in user.get("badges", [])],
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=user.get("score", user.get("points")),
            global_rank=user.get("rank"),
            finding_count=user.get("vulnerabilities", user.get("cves", user.get("report_count"))),
            raw_data={
                k: user[k]
                for k in ("cves", "plugins_reported", "severity_breakdown", "wordpress_plugins")
                if k in user
            },
        )

        return profile, snapshot
