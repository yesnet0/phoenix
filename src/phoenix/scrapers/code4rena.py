"""Code4rena scraper — Tier 1 (REST API / GitHub data).

Code4rena (C4) is a competitive audit platform for smart contracts.
Leaderboard data may be available via API or their public GitHub repo.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

BASE_URL = "https://code4rena.com"
GITHUB_DATA = "https://raw.githubusercontent.com/code-423n4"


@register_scraper("code4rena")
class Code4renaScraper(ApiScraper):
    platform_name = "code4rena"

    async def _fetch_leaderboard_data(self, max_entries: int) -> list[dict]:
        """Try API endpoints first, then GitHub raw data."""
        # Try REST API
        api_paths = [
            f"{BASE_URL}/api/v1/leaderboard",
            f"{BASE_URL}/api/leaderboard",
            f"{BASE_URL}/api/v1/wardens/leaderboard",
        ]
        for path in api_paths:
            try:
                resp = await self._get(path, params={"limit": max_entries})
                data = resp.json()
                if isinstance(data, list):
                    return data
                for key in ("data", "results", "leaderboard", "wardens"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
            except Exception:
                continue

        # Fallback: try public GitHub data
        github_paths = [
            f"{GITHUB_DATA}/code423n4.com/main/_data/handles.json",
            f"{GITHUB_DATA}/code423n4.com/main/_data/leaderboard.json",
        ]
        for path in github_paths:
            try:
                resp = await self._get(path)
                data = resp.json()
                if isinstance(data, list):
                    return data
            except Exception:
                continue

        # Fallback: try Next.js _next/data
        try:
            resp = await self._get(f"{BASE_URL}/leaderboard")
            html = resp.text
            build_match = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
            if build_match:
                build_id = build_match.group(1)
                resp = await self._get(f"{BASE_URL}/_next/data/{build_id}/leaderboard.json")
                page_props = resp.json().get("pageProps", {})
                for key in ("leaderboard", "wardens", "data"):
                    if key in page_props and isinstance(page_props[key], list):
                        return page_props[key]
        except Exception:
            pass

        return []

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        items = await self._fetch_leaderboard_data(max_entries)
        entries: list[LeaderboardEntry] = []

        for i, item in enumerate(items[:max_entries]):
            username = (
                item.get("handle")
                or item.get("username")
                or item.get("warden")
                or item.get("name", "")
            )
            if not username:
                continue
            entries.append(
                LeaderboardEntry(
                    username=username,
                    rank=item.get("rank", i + 1),
                    score=item.get("total", item.get("score", item.get("allTimeAwards"))),
                    profile_url=f"{BASE_URL}/@{username}",
                    extra={
                        k: item[k]
                        for k in ("findings", "highRisk", "medRisk", "gasOptimizations", "contests")
                        if k in item
                    },
                )
            )

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        user: dict = {}

        for path in (
            f"{BASE_URL}/api/v1/wardens/{username}",
            f"{BASE_URL}/api/wardens/{username}",
            f"{BASE_URL}/api/v1/users/{username}",
        ):
            try:
                resp = await self._get(path)
                data = resp.json()
                user = data.get("data", data) if isinstance(data, dict) else {}
                if user.get("handle") or user.get("username"):
                    break
                user = {}
            except Exception:
                continue

        if not user:
            raise ValueError(f"Code4rena profile not found: {username}")

        bio = user.get("bio", "") or ""
        urls = []
        if user.get("link"):
            urls.append(user["link"])
        if user.get("github"):
            urls.append(f"https://github.com/{user['github']}" if not user["github"].startswith("http") else user["github"])
        if user.get("twitter"):
            urls.append(f"https://twitter.com/{user['twitter']}" if not user["twitter"].startswith("http") else user["twitter"])

        social_links = extract_social_links(bio, urls)

        members = user.get("members", [])
        is_team = len(members) > 0

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=user.get("name", user.get("display_name", username)),
            bio=bio,
            location=user.get("location", ""),
            profile_url=f"{BASE_URL}/@{username}",
            social_links=social_links,
            badges=["team" if is_team else "solo"] + [str(b) for b in user.get("badges", [])],
            skill_tags=user.get("skills", []),
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=user.get("total", user.get("allTimeAwards", user.get("score"))),
            global_rank=user.get("rank"),
            finding_count=user.get("findings", user.get("total_findings")),
            total_earnings=user.get("total", user.get("allTimeAwards")),
            raw_data={
                k: user[k]
                for k in ("highRisk", "medRisk", "gasOptimizations", "contests", "qaReports")
                if k in user
            },
        )

        return profile, snapshot
