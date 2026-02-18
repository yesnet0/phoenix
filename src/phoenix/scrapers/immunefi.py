"""Immunefi scraper — Tier 1 (REST/Next.js API).

Immunefi is a Web3 bug bounty platform. Leaderboard data may come from
a REST API or a Next.js _next/data endpoint.
"""

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

BASE_URL = "https://immunefi.com"


@register_scraper("immunefi")
class ImmunefiScraper(ApiScraper):
    platform_name = "immunefi"

    async def _fetch_leaderboard_json(self, max_entries: int) -> list[dict]:
        """Try multiple known API patterns for leaderboard data."""
        api_paths = [
            "/api/leaderboard",
            "/api/v1/leaderboard",
            "/api/hackers/leaderboard",
        ]

        for path in api_paths:
            try:
                resp = await self._get(
                    f"{BASE_URL}{path}",
                    params={"limit": max_entries},
                )
                data = resp.json()
                # Handle both array and wrapped responses
                if isinstance(data, list):
                    return data
                for key in ("results", "data", "leaderboard", "items", "hackers"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
            except Exception:
                continue

        # Fallback: try _next/data route
        try:
            resp = await self._get(f"{BASE_URL}/leaderboard/")
            html = resp.text
            # Extract buildId from Next.js page source
            import re

            build_match = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
            if build_match:
                build_id = build_match.group(1)
                resp = await self._get(
                    f"{BASE_URL}/_next/data/{build_id}/leaderboard.json",
                )
                data = resp.json()
                page_props = data.get("pageProps", {})
                for key in ("leaderboard", "hackers", "results", "data"):
                    if key in page_props and isinstance(page_props[key], list):
                        return page_props[key]
        except Exception:
            log.warning("immunefi_nextjs_fallback_failed")

        return []

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        items = await self._fetch_leaderboard_json(max_entries)
        entries: list[LeaderboardEntry] = []

        for i, item in enumerate(items[:max_entries]):
            username = (
                item.get("username")
                or item.get("handle")
                or item.get("name")
                or item.get("id", "")
            )
            if not username:
                continue

            entries.append(
                LeaderboardEntry(
                    username=str(username),
                    rank=item.get("rank", i + 1),
                    score=item.get("totalPaidOut", item.get("total_paid", item.get("score"))),
                    profile_url=f"{BASE_URL}/profile/{username}",
                    extra={
                        k: item[k]
                        for k in ("totalBugs", "criticalBugs", "paidAmount", "boostedFindings")
                        if k in item
                    },
                )
            )

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        user: dict = {}
        profile_paths = [
            f"/api/hackers/{username}",
            f"/api/v1/profile/{username}",
            f"/api/profile/{username}",
        ]

        for path in profile_paths:
            try:
                resp = await self._get(f"{BASE_URL}{path}")
                data = resp.json()
                user = data if isinstance(data, dict) and ("username" in data or "handle" in data) else data.get("data", data.get("profile", {}))
                if user:
                    break
            except Exception:
                continue

        if not user:
            raise ValueError(f"Immunefi profile not found: {username}")

        bio = user.get("bio", "") or ""
        urls = [user[k] for k in ("website", "twitter", "github") if user.get(k)]
        social_links = extract_social_links(bio, urls)

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=user.get("name", user.get("display_name", "")),
            bio=bio,
            location=user.get("location", ""),
            profile_url=f"{BASE_URL}/profile/{username}",
            social_links=social_links,
            badges=[str(b) for b in user.get("badges", [])],
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=user.get("totalPaidOut", user.get("total_paid", user.get("score"))),
            global_rank=user.get("rank"),
            finding_count=user.get("totalBugs", user.get("bug_count")),
            total_earnings=user.get("totalPaidOut", user.get("total_paid")),
            raw_data={
                k: user[k]
                for k in ("criticalBugs", "highBugs", "mediumBugs", "paidAmount", "boostedFindings")
                if k in user
            },
        )

        return profile, snapshot
