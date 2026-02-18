"""CodeHawks scraper — Tier 1 (REST API).

CodeHawks (by Cyfrin) is a competitive smart contract audit platform.
"""

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

BASE_URL = "https://codehawks.cyfrin.io"
API_PATHS = [
    f"{BASE_URL}/api/leaderboard",
    f"{BASE_URL}/api/v1/leaderboard",
    "https://api.codehawks.cyfrin.io/leaderboard",
    "https://api.codehawks.cyfrin.io/v1/leaderboard",
]


@register_scraper("codehawks")
class CodeHawksScraper(ApiScraper):
    platform_name = "codehawks"

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        items: list[dict] = []

        for path in API_PATHS:
            try:
                resp = await self._get(path, params={"limit": max_entries, "page": 1})
                data = resp.json()
                if isinstance(data, list):
                    items = data
                else:
                    for key in ("data", "results", "leaderboard", "hawks", "auditors"):
                        if key in data and isinstance(data[key], list):
                            items = data[key]
                            break
                if items:
                    break
            except Exception:
                continue

        if not items:
            log.warning("codehawks_no_leaderboard_data")
            return []

        entries: list[LeaderboardEntry] = []
        for i, item in enumerate(items[:max_entries]):
            username = (
                item.get("handle")
                or item.get("username")
                or item.get("hawk")
                or item.get("name", "")
            )
            if not username:
                continue
            entries.append(
                LeaderboardEntry(
                    username=username,
                    rank=item.get("rank", i + 1),
                    score=item.get("totalPayout", item.get("xp", item.get("score"))),
                    profile_url=f"{BASE_URL}/profile/{username}",
                    extra={
                        k: item[k]
                        for k in ("highFindings", "mediumFindings", "lowFindings", "contests", "xp")
                        if k in item
                    },
                )
            )

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        user: dict = {}

        profile_paths = [
            f"{BASE_URL}/api/users/{username}",
            f"{BASE_URL}/api/v1/users/{username}",
            f"{BASE_URL}/api/hawks/{username}",
            f"https://api.codehawks.cyfrin.io/users/{username}",
        ]

        for path in profile_paths:
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
            raise ValueError(f"CodeHawks profile not found: {username}")

        bio = user.get("bio", "") or ""
        urls = [user[k] for k in ("github", "twitter", "website") if user.get(k)]
        social_links = extract_social_links(bio, urls)

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=user.get("name", user.get("displayName", "")),
            bio=bio,
            location=user.get("location", ""),
            profile_url=f"{BASE_URL}/profile/{username}",
            social_links=social_links,
            badges=[str(b) for b in user.get("badges", [])],
            skill_tags=user.get("skills", user.get("languages", [])),
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=user.get("totalPayout", user.get("xp", user.get("score"))),
            global_rank=user.get("rank"),
            finding_count=user.get("totalFindings"),
            total_earnings=user.get("totalPayout"),
            raw_data={
                k: user[k]
                for k in ("highFindings", "mediumFindings", "lowFindings", "contests", "xp", "level")
                if k in user
            },
        )

        return profile, snapshot
