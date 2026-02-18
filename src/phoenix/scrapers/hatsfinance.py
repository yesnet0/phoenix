"""Hats Finance scraper — Tier 1 (REST/Subgraph API).

Hats Finance is a decentralized bug bounty protocol. Data may be available
via a REST API or a blockchain subgraph query.
"""

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

APP_URL = "https://app.hats.finance"

# Common subgraph endpoints for Hats Finance
SUBGRAPH_URLS = [
    "https://api.thegraph.com/subgraphs/name/hats-finance/hats",
    "https://api.thegraph.com/subgraphs/name/hats-finance/hats-v2",
]

LEADERBOARD_QUERY = """
{
  hackers(first: %d, orderBy: totalPayout, orderDirection: desc) {
    id
    address
    totalPayout
    totalFindings
    highFindings
    mediumFindings
    lowFindings
    createdAt
  }
}
"""

HACKER_QUERY = """
{
  hacker(id: "%s") {
    id
    address
    totalPayout
    totalFindings
    highFindings
    mediumFindings
    lowFindings
    vaults
    createdAt
  }
}
"""


@register_scraper("hatsfinance")
class HatsFinanceScraper(ApiScraper):
    platform_name = "hatsfinance"

    async def _subgraph_query(self, query: str) -> dict | None:
        """Execute a GraphQL query against known subgraph endpoints."""
        for url in SUBGRAPH_URLS:
            try:
                resp = await self._post(url, json={"query": query})
                data = resp.json()
                if "data" in data:
                    return data["data"]
            except Exception:
                continue
        return None

    async def _try_rest_api(self, path: str, params: dict | None = None) -> dict | list | None:
        """Try REST API endpoints."""
        api_bases = [
            f"{APP_URL}/api",
            "https://api.hats.finance",
            "https://api.hats.finance/v1",
        ]
        for base in api_bases:
            try:
                resp = await self._get(f"{base}{path}", params=params or {})
                return resp.json()
            except Exception:
                continue
        return None

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        # Try REST API first
        data = await self._try_rest_api("/leaderboard", {"limit": max_entries})
        items: list[dict] = []

        if data is not None:
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for key in ("data", "results", "leaderboard", "hackers"):
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break

        # Fallback to subgraph
        if not items:
            result = await self._subgraph_query(LEADERBOARD_QUERY % max_entries)
            if result:
                items = result.get("hackers", [])

        entries: list[LeaderboardEntry] = []
        for i, item in enumerate(items[:max_entries]):
            # Hats uses addresses or handles
            username = (
                item.get("handle")
                or item.get("username")
                or item.get("address")
                or item.get("id", "")
            )
            if not username:
                continue

            payout = item.get("totalPayout", item.get("total_payout", item.get("score")))
            if isinstance(payout, str):
                try:
                    payout = float(payout) / 1e18  # Convert from wei if needed
                except (ValueError, TypeError):
                    payout = None

            entries.append(
                LeaderboardEntry(
                    username=username,
                    rank=item.get("rank", i + 1),
                    score=payout,
                    profile_url=f"{APP_URL}/profile/{username}",
                    extra={
                        k: item[k]
                        for k in ("totalFindings", "highFindings", "mediumFindings", "lowFindings", "vaults")
                        if k in item
                    },
                )
            )

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        user: dict = {}

        # Try REST API
        data = await self._try_rest_api(f"/hackers/{username}")
        if data:
            user = data.get("data", data) if isinstance(data, dict) else {}

        # Fallback to subgraph
        if not user or not (user.get("address") or user.get("handle")):
            result = await self._subgraph_query(HACKER_QUERY % username)
            if result:
                user = result.get("hacker", {}) or {}

        if not user:
            raise ValueError(f"Hats Finance profile not found: {username}")

        bio = user.get("bio", "") or ""
        urls = [user[k] for k in ("github", "twitter", "website") if user.get(k)]
        social_links = extract_social_links(bio, urls)

        display_name = user.get("name", user.get("handle", ""))
        address = user.get("address", "")
        if not display_name and address:
            display_name = f"{address[:6]}...{address[-4:]}" if len(address) > 10 else address

        payout = user.get("totalPayout", user.get("total_payout"))
        if isinstance(payout, str):
            try:
                payout = float(payout) / 1e18
            except (ValueError, TypeError):
                payout = None

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=display_name,
            bio=bio,
            profile_url=f"{APP_URL}/profile/{username}",
            social_links=social_links,
        )

        total_findings = user.get("totalFindings")
        if isinstance(total_findings, str):
            try:
                total_findings = int(total_findings)
            except (ValueError, TypeError):
                total_findings = None

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=payout,
            global_rank=user.get("rank"),
            finding_count=total_findings,
            total_earnings=payout,
            raw_data={
                k: user[k]
                for k in ("highFindings", "mediumFindings", "lowFindings", "vaults", "address")
                if k in user
            },
        )

        return profile, snapshot
