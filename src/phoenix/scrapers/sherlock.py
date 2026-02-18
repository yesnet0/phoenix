"""Sherlock scraper — Tier 1 (REST API).

Sherlock is a Web3 audit contest platform. Leaderboard data is served from
their contest API at mainnet-contest.sherlock.xyz or similar endpoints.
"""

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

APP_URL = "https://app.sherlock.xyz"
API_BASES = [
    "https://mainnet-contest.sherlock.xyz",
    "https://app.sherlock.xyz/api",
    "https://api.sherlock.xyz",
]


@register_scraper("sherlock")
class SherlockScraper(ApiScraper):
    platform_name = "sherlock"

    async def _api_get(self, path: str, params: dict | None = None) -> dict | list | None:
        """Try the path against all known API base URLs."""
        for base in API_BASES:
            try:
                resp = await self._get(f"{base}{path}", params=params or {})
                return resp.json()
            except Exception:
                continue
        return None

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        data = await self._api_get("/leaderboard")
        if data is None:
            data = await self._api_get("/auditors/leaderboard")
        if data is None:
            data = await self._api_get("/v1/leaderboard")

        if data is None:
            log.warning("sherlock_no_leaderboard_data")
            return []

        items = data if isinstance(data, list) else data.get("data", data.get("leaderboard", data.get("auditors", [])))
        entries: list[LeaderboardEntry] = []

        for i, item in enumerate(items[:max_entries]):
            username = (
                item.get("handle")
                or item.get("username")
                or item.get("auditor")
                or ""
            )
            if not username:
                continue
            entries.append(
                LeaderboardEntry(
                    username=username,
                    rank=item.get("rank", i + 1),
                    score=item.get("totalPayout", item.get("score", item.get("points"))),
                    profile_url=f"{APP_URL}/audits/leaderboard",
                    extra={
                        k: item[k]
                        for k in ("contests", "highFindings", "mediumFindings", "totalFindings")
                        if k in item
                    },
                )
            )

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        user = await self._api_get(f"/auditors/{username}")
        if user is None:
            user = await self._api_get(f"/users/{username}")
        if user is None:
            user = await self._api_get(f"/v1/auditors/{username}")

        if not user or (isinstance(user, dict) and not (user.get("handle") or user.get("username"))):
            if isinstance(user, dict):
                user = user.get("data", user.get("auditor", {}))

        if not user:
            raise ValueError(f"Sherlock profile not found: {username}")

        bio = user.get("bio", "") or ""
        urls = [user[k] for k in ("github", "twitter", "website") if user.get(k)]
        social_links = extract_social_links(bio, urls)

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=user.get("name", user.get("displayName", "")),
            bio=bio,
            location=user.get("location", ""),
            profile_url=f"{APP_URL}/audits/leaderboard",
            social_links=social_links,
            badges=[str(b) for b in user.get("badges", [])],
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=user.get("totalPayout", user.get("score")),
            global_rank=user.get("rank"),
            finding_count=user.get("totalFindings", user.get("finding_count")),
            total_earnings=user.get("totalPayout", user.get("earnings")),
            raw_data={
                k: user[k]
                for k in (
                    "highFindings", "mediumFindings", "contests",
                    "judging_contests", "lead_judge_contests",
                )
                if k in user
            },
        )

        return profile, snapshot
