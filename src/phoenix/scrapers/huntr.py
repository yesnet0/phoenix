"""Huntr scraper — Tier 1 (Next.js/REST API).

Huntr is a security vulnerability bounty platform focused on open source.
Built with Next.js, likely has API or _next/data endpoints.
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

BASE_URL = "https://huntr.dev"


@register_scraper("huntr")
class HuntrScraper(ApiScraper):
    platform_name = "huntr"

    async def _try_api_endpoints(self, path_variants: list[str], params: dict | None = None) -> dict | list | None:
        """Try multiple API path patterns, return first successful JSON."""
        for path in path_variants:
            try:
                resp = await self._get(f"{BASE_URL}{path}", params=params or {})
                return resp.json()
            except Exception:
                continue
        return None

    async def _try_nextjs_data(self, page_path: str) -> dict | None:
        """Try to fetch data via Next.js _next/data route."""
        try:
            resp = await self._get(f"{BASE_URL}/{page_path}")
            html = resp.text
            build_match = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
            if build_match:
                build_id = build_match.group(1)
                json_path = page_path.rstrip("/") or "index"
                resp = await self._get(f"{BASE_URL}/_next/data/{build_id}/{json_path}.json")
                return resp.json().get("pageProps", {})
        except Exception:
            log.debug("huntr_nextjs_fallback_failed", page=page_path)
        return None

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        data = await self._try_api_endpoints(
            [
                "/api/leaderboard",
                "/api/v1/leaderboard",
                "/api/hackers/leaderboard",
                "/api/users/leaderboard",
            ],
            params={"limit": max_entries},
        )

        if data is None:
            nextjs = await self._try_nextjs_data("leaderboard")
            if nextjs:
                data = nextjs.get("leaderboard", nextjs.get("users", nextjs.get("data")))

        if data is None:
            log.warning("huntr_no_leaderboard_data")
            return []

        items = data if isinstance(data, list) else data.get("data", data.get("leaderboard", data.get("users", [])))
        entries: list[LeaderboardEntry] = []

        for i, item in enumerate(items[:max_entries]):
            username = item.get("username", item.get("handle", item.get("login", "")))
            if not username:
                continue
            entries.append(
                LeaderboardEntry(
                    username=username,
                    rank=item.get("rank", i + 1),
                    score=item.get("bounties", item.get("score", item.get("points"))),
                    profile_url=f"{BASE_URL}/users/{username}",
                    extra={
                        k: item[k]
                        for k in ("disclosures", "cves", "fixCount", "severity_breakdown")
                        if k in item
                    },
                )
            )

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        data = await self._try_api_endpoints(
            [
                f"/api/users/{username}",
                f"/api/v1/users/{username}",
                f"/api/hackers/{username}",
            ],
        )

        if data is None:
            nextjs = await self._try_nextjs_data(f"users/{username}")
            if nextjs:
                data = nextjs.get("user", nextjs.get("profile", nextjs))

        if not data or (isinstance(data, dict) and not (data.get("username") or data.get("handle"))):
            user = data if isinstance(data, dict) else {}
        else:
            user = data.get("data", data) if isinstance(data, dict) else {}

        if not user:
            raise ValueError(f"Huntr profile not found: {username}")

        bio = user.get("bio", "") or ""
        urls = [user[k] for k in ("website", "github", "twitter") if user.get(k)]
        social_links = extract_social_links(bio, urls)

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=user.get("name", user.get("displayName", "")),
            bio=bio,
            location=user.get("location", ""),
            profile_url=f"{BASE_URL}/users/{username}",
            social_links=social_links,
            badges=[str(b) for b in user.get("badges", [])],
            skill_tags=user.get("languages", user.get("skills", [])),
            join_date=user.get("created_at", user.get("joinedAt")),
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=user.get("bounties", user.get("score", user.get("points"))),
            global_rank=user.get("rank"),
            finding_count=user.get("disclosures", user.get("vulnerability_count")),
            raw_data={
                k: user[k]
                for k in ("cves", "fixCount", "severity_breakdown", "total_bounty")
                if k in user
            },
        )

        return profile, snapshot
