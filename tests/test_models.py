"""Test Pydantic models and normalizer."""

from phoenix.models.researcher import (
    IdentityLink,
    PlatformProfile,
    ProfileSnapshot,
    Researcher,
    SocialLink,
    SocialPlatform,
)
from phoenix.models.platform import Platform, ScraperTier, PLATFORMS
from phoenix.models.scrape import ScrapeJob, ScrapeResult, ScrapeStatus
from phoenix.scrapers.utils.normalizer import extract_social_links, normalize_handle


def test_platform_profile_defaults():
    p = PlatformProfile(platform_name="hackerone", username="alice")
    assert p.platform_name == "hackerone"
    assert p.username == "alice"
    assert p.id  # auto-generated UUID
    assert p.social_links == []
    assert p.badges == []


def test_profile_snapshot_defaults():
    s = ProfileSnapshot(profile_id="abc")
    assert s.profile_id == "abc"
    assert s.overall_score is None
    assert s.raw_data == {}


def test_identity_link_defaults():
    link = IdentityLink(key_type="github", key_value="alice")
    assert link.confidence == 1.0
    assert link.resolved_by == "identity_pipeline"


def test_researcher_defaults():
    r = Researcher()
    assert r.composite_score == 0.0
    assert r.profile_ids == []


def test_platforms_seed_data():
    assert len(PLATFORMS) == 3
    names = {p.name for p in PLATFORMS}
    assert names == {"hackerone", "bugcrowd", "intigriti"}


def test_scrape_job_defaults():
    job = ScrapeJob(platform_name="hackerone")
    assert job.status == ScrapeStatus.PENDING
    assert job.max_profiles == 50


def test_normalize_handle():
    assert normalize_handle("@Alice") == "alice"
    assert normalize_handle("  Bob  ") == "bob"


def test_extract_social_links_twitter():
    links = extract_social_links("Follow me https://twitter.com/alice123", [])
    assert any(l.platform == SocialPlatform.TWITTER and l.handle == "alice123" for l in links)


def test_extract_social_links_github():
    links = extract_social_links("", ["https://github.com/bob-dev"])
    assert any(l.platform == SocialPlatform.GITHUB and l.handle == "bob-dev" for l in links)


def test_extract_social_links_email():
    links = extract_social_links("Contact: alice@example.com for collabs", [])
    assert any(l.platform == SocialPlatform.EMAIL and l.handle == "alice@example.com" for l in links)


def test_extract_social_links_dedup():
    links = extract_social_links(
        "https://twitter.com/alice",
        ["https://twitter.com/alice", "https://twitter.com/alice"],
    )
    twitter_links = [l for l in links if l.platform == SocialPlatform.TWITTER]
    assert len(twitter_links) == 1


def test_extract_social_links_website():
    links = extract_social_links("", ["https://myblog.com/about"])
    assert any(l.platform == SocialPlatform.WEBSITE and l.handle == "myblog.com" for l in links)
