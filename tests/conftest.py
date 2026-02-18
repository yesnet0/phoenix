"""Shared test fixtures."""

import pytest
from phoenix.models.researcher import (
    PlatformProfile,
    ProfileSnapshot,
    SocialLink,
    SocialPlatform,
)


@pytest.fixture
def sample_profile():
    return PlatformProfile(
        platform_name="hackerone",
        username="testuser",
        display_name="Test User",
        bio="Security researcher. GitHub: https://github.com/testuser",
        location="Earth",
        profile_url="https://hackerone.com/testuser",
        social_links=[
            SocialLink(platform=SocialPlatform.GITHUB, handle="testuser", raw_value="https://github.com/testuser"),
            SocialLink(platform=SocialPlatform.TWITTER, handle="testuser", raw_value="https://twitter.com/testuser"),
        ],
        badges=["triager"],
        skill_tags=["web", "api"],
    )


@pytest.fixture
def sample_snapshot(sample_profile):
    return ProfileSnapshot(
        profile_id=sample_profile.id,
        overall_score=1500.0,
        global_rank=42,
        signal_percentile=95.0,
        impact_percentile=88.0,
        finding_count=120,
        critical_count=5,
        high_count=25,
        medium_count=50,
        low_count=40,
    )
