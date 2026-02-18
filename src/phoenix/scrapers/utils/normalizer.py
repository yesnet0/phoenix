"""Normalize social handles, URLs, and emails."""

import re
from urllib.parse import urlparse

from phoenix.models.researcher import SocialLink, SocialPlatform

# Patterns for extracting handles from URLs
_TWITTER_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/(@?[\w]+)", re.I)
_GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/([\w\-]+)", re.I)
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/([\w\-]+)", re.I)
_MASTODON_RE = re.compile(r"@?([\w]+)@([\w\.\-]+)", re.I)
_EMAIL_RE = re.compile(r"[\w\.\+\-]+@[\w\.\-]+\.\w+")


def normalize_handle(raw: str) -> str:
    """Strip @, leading/trailing whitespace, lowercase."""
    return raw.strip().lstrip("@").lower()


def extract_social_links(text: str, urls: list[str] | None = None) -> list[SocialLink]:
    """Extract and normalize social links from text and URL list."""
    links: list[SocialLink] = []
    all_text = text + " " + " ".join(urls or [])

    # Twitter/X
    for m in _TWITTER_RE.finditer(all_text):
        handle = normalize_handle(m.group(1))
        if handle not in ("intent", "share", "home"):
            links.append(SocialLink(platform=SocialPlatform.TWITTER, handle=handle, raw_value=m.group(0)))

    # GitHub
    for m in _GITHUB_RE.finditer(all_text):
        handle = normalize_handle(m.group(1))
        if handle not in ("orgs", "settings", "notifications", "sponsors"):
            links.append(SocialLink(platform=SocialPlatform.GITHUB, handle=handle, raw_value=m.group(0)))

    # LinkedIn
    for m in _LINKEDIN_RE.finditer(all_text):
        handle = normalize_handle(m.group(1))
        links.append(SocialLink(platform=SocialPlatform.LINKEDIN, handle=handle, raw_value=m.group(0)))

    # Mastodon
    for m in _MASTODON_RE.finditer(all_text):
        handle = f"{m.group(1).lower()}@{m.group(2).lower()}"
        links.append(SocialLink(platform=SocialPlatform.MASTODON, handle=handle, raw_value=m.group(0)))

    # Email
    for m in _EMAIL_RE.finditer(all_text):
        links.append(SocialLink(platform=SocialPlatform.EMAIL, handle=m.group(0).lower(), raw_value=m.group(0)))

    # Remaining URLs → website
    for url in urls or []:
        parsed = urlparse(url if url.startswith("http") else f"https://{url}")
        if parsed.hostname and not any(
            d in (parsed.hostname or "")
            for d in ("twitter.com", "x.com", "github.com", "linkedin.com", "hackerone.com", "bugcrowd.com")
        ):
            links.append(SocialLink(platform=SocialPlatform.WEBSITE, handle=parsed.hostname, raw_value=url))

    # Deduplicate by (platform, handle)
    seen: set[tuple[str, str]] = set()
    deduped: list[SocialLink] = []
    for link in links:
        key = (link.platform.value, link.handle)
        if key not in seen:
            seen.add(key)
            deduped.append(link)

    return deduped
