"""Topcoder scraper — Tier 1 (Public REST API).

Topcoder has a well-documented public API at api.topcoder.com/v5.
"""

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

API_BASE = "https://api.topcoder.com/v5"
SITE_URL = "https://www.topcoder.com"


@register_scraper("topcoder")
class TopcoderScraper(ApiScraper):
    platform_name = "topcoder"

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        """Fetch top members from the Topcoder API.

        Uses the members endpoint with sorting by rating/wins for
        security-related challenge types.
        """
        entries: list[LeaderboardEntry] = []
        offset = 0
        limit = min(max_entries, 50)

        while len(entries) < max_entries:
            # Try leaderboard-specific endpoints first
            data = None
            endpoints = [
                (f"{API_BASE}/leaderboard", {"limit": limit, "offset": offset}),
                (
                    f"{API_BASE}/members",
                    {
                        "limit": limit,
                        "offset": offset,
                        "sort": "rating desc",
                        "fields": "handle,maxRating,wins,userId,country",
                    },
                ),
                (
                    "https://api.topcoder.com/v3/leaderboards",
                    {"limit": limit, "offset": offset},
                ),
            ]

            for url, params in endpoints:
                try:
                    resp = await self._get(url, params=params)
                    data = resp.json()
                    break
                except Exception:
                    continue

            if data is None:
                break

            # Handle various response shapes
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = (
                    data.get("result", {}).get("content", [])
                    or data.get("data", [])
                    or data.get("results", [])
                    or data.get("members", [])
                )
            else:
                break

            if not items:
                break

            for i, item in enumerate(items):
                handle = item.get("handle", item.get("username", ""))
                if not handle:
                    continue

                rating = (
                    item.get("maxRating", {}).get("rating")
                    if isinstance(item.get("maxRating"), dict)
                    else item.get("maxRating", item.get("rating", item.get("score")))
                )

                entries.append(
                    LeaderboardEntry(
                        username=handle,
                        rank=item.get("rank", offset + i + 1),
                        score=rating,
                        profile_url=f"{SITE_URL}/members/{handle}",
                        extra={
                            k: item[k]
                            for k in ("wins", "challenges", "country", "userId", "track")
                            if k in item
                        },
                    )
                )
                if len(entries) >= max_entries:
                    break

            offset += limit
            if len(items) < limit:
                break

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        """Fetch a Topcoder member profile via the public API."""
        user: dict = {}

        # Primary endpoint
        try:
            resp = await self._get(f"{API_BASE}/members/{username}")
            data = resp.json()
            # v5 may return directly or nested in result
            if isinstance(data, dict):
                user = data.get("result", {}).get("content", data) if "result" in data else data
        except Exception:
            pass

        if not user or not (user.get("handle") or user.get("userId")):
            # Try v3 fallback
            try:
                resp = await self._get(f"https://api.topcoder.com/v3/members/{username}")
                data = resp.json()
                user = data.get("result", {}).get("content", data) if isinstance(data, dict) else {}
            except Exception:
                pass

        if not user:
            raise ValueError(f"Topcoder member not found: {username}")

        # Fetch stats separately if available
        stats: dict = {}
        try:
            resp = await self._get(f"{API_BASE}/members/{username}/stats")
            stats_data = resp.json()
            if isinstance(stats_data, dict):
                stats = stats_data.get("result", {}).get("content", stats_data) if "result" in stats_data else stats_data
            elif isinstance(stats_data, list) and stats_data:
                stats = stats_data[0]
        except Exception:
            pass

        bio = user.get("description", "") or user.get("shortBio", "") or ""
        urls = []
        if user.get("homeCountryCode"):
            pass  # Not a URL
        if user.get("photoURL"):
            pass  # Avatar, not social
        # Topcoder external links
        external = user.get("externalLinks", []) or []
        for link in external:
            if isinstance(link, dict) and link.get("URL"):
                urls.append(link["URL"])
            elif isinstance(link, str):
                urls.append(link)

        social_links = extract_social_links(bio, urls)

        # Build skill tags from stats
        skill_tags: list[str] = []
        if isinstance(stats, dict):
            for track_name in ("DATA_SCIENCE", "DEVELOP", "DESIGN", "COPILOT"):
                track = stats.get(track_name, stats.get(track_name.lower()))
                if track and isinstance(track, dict):
                    for subtrack in track.get("subTracks", track.get("subtracks", [])):
                        if isinstance(subtrack, dict) and subtrack.get("name"):
                            skill_tags.append(subtrack["name"])

        max_rating = user.get("maxRating", {})
        if isinstance(max_rating, dict):
            rating_val = max_rating.get("rating")
        else:
            rating_val = max_rating or user.get("rating")

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=user.get("firstName", "") + (" " + user.get("lastName", "")).rstrip(),
            bio=bio,
            location=user.get("homeCountryCode", user.get("country", "")),
            profile_url=f"{SITE_URL}/members/{username}",
            social_links=social_links,
            badges=[str(b) for b in user.get("badges", user.get("achievements", []))],
            skill_tags=skill_tags[:20],
            join_date=user.get("createdAt", user.get("memberSince")),
        )

        # Aggregate wins from stats
        total_wins = user.get("wins", 0)
        total_challenges = user.get("challenges", 0)
        if isinstance(stats, dict):
            total_wins = total_wins or stats.get("wins", 0)
            total_challenges = total_challenges or stats.get("challenges", 0)

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=rating_val,
            global_rank=user.get("rank"),
            finding_count=total_challenges or None,
            acceptance_rate=(total_wins / total_challenges) if total_challenges and total_wins else None,
            raw_data={
                "wins": total_wins,
                "challenges": total_challenges,
                "userId": user.get("userId"),
                "country": user.get("homeCountryCode"),
                "member_since": user.get("memberSince"),
                "photo_url": user.get("photoURL"),
            },
        )

        return profile, snapshot
