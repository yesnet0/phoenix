"""HackenProof scraper — Tier 1 (REST API).

HackenProof is a Web3-focused bug bounty platform with a public leaderboard.
"""

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

BASE_URL = "https://hackenproof.com"
API_BASE = "https://hackenproof.com/api"


@register_scraper("hackenproof")
class HackenProofScraper(ApiScraper):
    platform_name = "hackenproof"

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        entries: list[LeaderboardEntry] = []
        page = 1
        per_page = min(max_entries, 50)

        while len(entries) < max_entries:
            resp = None
            # Try versioned and unversioned API paths
            for path in (
                f"{API_BASE}/v1/leaderboard",
                f"{API_BASE}/leaderboard",
                f"{API_BASE}/v1/hackers/leaderboard",
            ):
                try:
                    resp = await self._get(
                        path,
                        params={"page": page, "per_page": per_page},
                    )
                    break
                except Exception:
                    continue

            if resp is None:
                log.warning("hackenproof_leaderboard_no_api")
                break

            data = resp.json()
            items = data if isinstance(data, list) else data.get("data", data.get("results", data.get("leaderboard", [])))

            if not items:
                break

            for item in items:
                username = item.get("username", item.get("handle", ""))
                if not username:
                    continue
                entries.append(
                    LeaderboardEntry(
                        username=username,
                        rank=item.get("rank", item.get("position")),
                        score=item.get("reputation", item.get("score", item.get("points"))),
                        profile_url=f"{BASE_URL}/hackers/{username}",
                        extra={
                            k: item[k]
                            for k in ("bug_count", "reward_total", "country")
                            if k in item
                        },
                    )
                )
                if len(entries) >= max_entries:
                    break

            # Pagination check
            meta = data.get("meta", {}) if isinstance(data, dict) else {}
            total_pages = meta.get("last_page", meta.get("total_pages", page))
            if page >= total_pages:
                break
            page += 1

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        user: dict = {}

        for path in (
            f"{API_BASE}/v1/hackers/{username}",
            f"{API_BASE}/hackers/{username}",
            f"{API_BASE}/v1/users/{username}",
        ):
            try:
                resp = await self._get(path)
                data = resp.json()
                user = data.get("data", data) if isinstance(data, dict) else {}
                if user.get("username") or user.get("handle"):
                    break
                user = {}
            except Exception:
                continue

        if not user:
            raise ValueError(f"HackenProof profile not found: {username}")

        bio = user.get("bio", "") or ""
        urls = [user[k] for k in ("website", "twitter_url", "github_url", "linkedin_url") if user.get(k)]
        social_links = extract_social_links(bio, urls)

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=user.get("name", user.get("display_name", "")),
            bio=bio,
            location=user.get("country", user.get("location", "")),
            profile_url=f"{BASE_URL}/hackers/{username}",
            social_links=social_links,
            badges=[str(b) for b in user.get("badges", [])],
            skill_tags=user.get("skills", []),
            join_date=user.get("created_at"),
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=user.get("reputation", user.get("score", user.get("points"))),
            global_rank=user.get("rank", user.get("position")),
            finding_count=user.get("bug_count", user.get("report_count")),
            total_earnings=user.get("reward_total", user.get("total_earned")),
            acceptance_rate=user.get("acceptance_rate"),
            raw_data={
                k: user[k]
                for k in ("critical_count", "high_count", "medium_count", "low_count", "streak")
                if k in user
            },
        )

        return profile, snapshot
