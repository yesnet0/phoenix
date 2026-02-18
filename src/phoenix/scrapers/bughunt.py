"""BugHunt scraper — Tier 3 (Playwright, Brazilian platform, possibly static/light JS).

Leaderboard: https://bughunt.com.br/ranking-bughunters.html
Profile: https://bughunt.com.br/bughunter/{username}
"""

import re

from phoenix.core.logging import get_logger
from phoenix.models.researcher import PlatformProfile, ProfileSnapshot
from phoenix.scrapers.base import LeaderboardEntry, PlaywrightScraper
from phoenix.scrapers.registry import register_scraper
from phoenix.scrapers.utils.normalizer import extract_social_links

log = get_logger(__name__)

LEADERBOARD_URL = "https://bughunt.com.br/ranking-bughunters.html"
PROFILE_BASE = "https://bughunt.com.br/bughunter"


@register_scraper("bughunt")
class BughuntScraper(PlaywrightScraper):
    platform_name = "bughunt"

    async def scrape_leaderboard(self, max_entries: int = 100) -> list[LeaderboardEntry]:
        page = await self._new_page()
        entries: list[LeaderboardEntry] = []

        try:
            await page.goto(LEADERBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            lines = [l.strip() for l in body.split("\n") if l.strip()]

            # Brazilian platform may use Portuguese labels
            for i, line in enumerate(lines):
                rank_match = re.match(r"^#?(\d+)[\.:]?$", line)
                if rank_match and i + 1 < len(lines):
                    rank = int(rank_match.group(1))
                    username = lines[i + 1].strip()
                    if not username or re.match(r"^[\d#]", username):
                        continue

                    score = None
                    for offset in range(2, 5):
                        if i + offset < len(lines):
                            score_match = re.match(
                                r"^([\d.,]+)\s*(?:pts|pontos|points)?$",
                                lines[i + offset],
                                re.I,
                            )
                            if score_match:
                                # Handle Brazilian number format (1.000,50)
                                raw_score = score_match.group(1)
                                if "," in raw_score and "." in raw_score:
                                    raw_score = raw_score.replace(".", "").replace(",", ".")
                                else:
                                    raw_score = raw_score.replace(",", "")
                                score = float(raw_score)
                                break

                    entries.append(
                        LeaderboardEntry(
                            username=username,
                            rank=rank,
                            score=score,
                            profile_url=f"{PROFILE_BASE}/{username}",
                        )
                    )

                    if len(entries) >= max_entries:
                        break

            log.info("bughunt_leaderboard_scraped", entries=len(entries))

        finally:
            await page.context.close()

        return entries

    async def scrape_profile(self, username: str) -> tuple[PlatformProfile, ProfileSnapshot]:
        page = await self._new_page()

        try:
            profile_url = f"{PROFILE_BASE}/{username}"
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookies(page)
            body = await self._get_body_text(page)

            raw_data: dict = {}
            rank = None
            score = None
            finding_count = None
            acceptance_rate = None

            # Support Portuguese labels
            rank_match = re.search(r"(?:Rank|Posi[cç][aã]o|Position)\s*[:#]?\s*(\d+)", body, re.I)
            if rank_match:
                rank = int(rank_match.group(1))
                raw_data["rank"] = rank

            score_match = re.search(r"(?:Points|Pontos|Score|Reputa[cç][aã]o)\s*[:#]?\s*([\d.,]+)", body, re.I)
            if score_match:
                raw_score = score_match.group(1)
                if "," in raw_score and "." in raw_score:
                    raw_score = raw_score.replace(".", "").replace(",", ".")
                else:
                    raw_score = raw_score.replace(",", "")
                score = float(raw_score)
                raw_data["score"] = score

            bugs_match = re.search(
                r"(?:Reports?|Bugs?|Findings?|Vulnerabilidades?|Relat[oó]rios?)\s*[:#]?\s*(\d+)",
                body,
                re.I,
            )
            if bugs_match:
                finding_count = int(bugs_match.group(1))
                raw_data["finding_count"] = finding_count

            acc_match = re.search(r"(?:Acceptance|Aceita[cç][aã]o|Valid)\s*(?:Rate)?\s*[:#]?\s*([\d.]+)\s*%", body, re.I)
            if acc_match:
                acceptance_rate = float(acc_match.group(1))
                raw_data["acceptance_rate"] = acceptance_rate

            programs_match = re.search(r"(?:Programs?|Programas?)\s*[:#]?\s*(\d+)", body, re.I)
            if programs_match:
                raw_data["programs"] = int(programs_match.group(1))

            for severity in ["Critical", "High", "Medium", "Low", "Cr[ií]tico", "Alto", "M[eé]dio", "Baixo"]:
                sev_match = re.search(rf"{severity}\s*[:#]?\s*(\d+)", body, re.I)
                if sev_match:
                    key = severity.lower()
                    # Normalize Portuguese severity names
                    for pt, en in [("cr", "critical"), ("alto", "high"), ("m", "medium"), ("baixo", "low")]:
                        if key.startswith(pt):
                            key = en
                            break
                    raw_data[key] = int(sev_match.group(1))

            external_links = await self._get_all_links(page, exclude_domain="bughunt.com.br")
            social_links = extract_social_links(body, external_links)

            profile = PlatformProfile(
                platform_name=self.platform_name,
                username=username,
                display_name=username,
                profile_url=profile_url,
                social_links=social_links,
            )

            snapshot = ProfileSnapshot(
                profile_id=profile.id,
                overall_score=score,
                global_rank=rank,
                finding_count=finding_count,
                acceptance_rate=acceptance_rate,
                critical_count=raw_data.get("critical"),
                high_count=raw_data.get("high"),
                medium_count=raw_data.get("medium"),
                low_count=raw_data.get("low"),
                raw_data=raw_data,
            )

            return profile, snapshot

        finally:
            await page.context.close()
