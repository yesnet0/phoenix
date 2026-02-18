"""YesWeHack scraper — Tier 1 (Public REST API).

API: https://api.yeswehack.com/ranking (paginated, 25 per page, 100 total)
Profile: https://api.yeswehack.com/hunters/{slug}
"""

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot, SocialLink, SocialPlatform
from phoenix.scrapers.base import ApiScraper, LeaderboardEntry
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links, normalize_handle
from phoenix.scrapers.utils.retry import scrape_retry

log = get_logger(__name__)

API_BASE = "https://api.yeswehack.com"


@register_scraper("yeswehack")
class YesWeHackScraper(ApiScraper):
    platform_name = "yeswehack"

    @scrape_retry
    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        entries: list[LeaderboardEntry] = []
        page = 1

        while len(entries) < max_entries:
            resp = await self._get(
                f"{API_BASE}/ranking",
                params={"page": page},
            )
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                username = item.get("username", "")
                slug = item.get("slug", username)
                if not username:
                    continue
                entries.append(
                    LeaderboardEntry(
                        username=slug,
                        rank=item.get("rank"),
                        score=item.get("points"),
                        profile_url=f"https://yeswehack.com/hunters/{slug}",
                        extra={"display_username": username},
                    )
                )
                if len(entries) >= max_entries:
                    break

            pagination = data.get("pagination", {})
            if page >= pagination.get("nb_pages", page):
                break
            page += 1

        return entries

    @scrape_retry
    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        resp = await self._get(f"{API_BASE}/hunters/{username}")
        user = resp.json()

        if not user or not user.get("username"):
            raise ValueError(f"YesWeHack user not found: {username}")

        hp = user.get("hunter_profile", {})
        social_links: list[SocialLink] = []

        if hp.get("twitter"):
            handle = normalize_handle(hp["twitter"])
            social_links.append(SocialLink(platform=SocialPlatform.TWITTER, handle=handle, raw_value=hp["twitter"]))
        if hp.get("github"):
            handle = normalize_handle(hp["github"])
            social_links.append(SocialLink(platform=SocialPlatform.GITHUB, handle=handle, raw_value=hp["github"]))

        bio = ""
        urls = []
        if hp.get("website_url"):
            urls.append(hp["website_url"])
        bio_links = extract_social_links(bio, urls)
        existing = {(l.platform, l.handle) for l in social_links}
        for link in bio_links:
            if (link.platform, link.handle) not in existing:
                social_links.append(link)

        display_name = " ".join(
            filter(None, [user.get("public_firstname"), user.get("public_lastname")])
        ) or user.get("username", "")

        profile = PlatformProfile(
            platform_name=self.platform_name,
            username=username,
            display_name=display_name,
            profile_url=f"https://yeswehack.com/hunters/{username}",
            location=user.get("nationality", ""),
            social_links=social_links,
            skill_tags=hp.get("skills", []),
            join_date=user.get("joined_on"),
        )

        snapshot = ProfileSnapshot(
            profile_id=profile.id,
            overall_score=user.get("points"),
            global_rank=user.get("rank"),
            finding_count=user.get("nb_reports"),
            raw_data={
                "impact": user.get("impact"),
                "kyc_status": user.get("kyc_status"),
            },
        )

        return profile, snapshot
