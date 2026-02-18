"""Researcher and identity models."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class SocialPlatform(StrEnum):
    TWITTER = "twitter"
    GITHUB = "github"
    LINKEDIN = "linkedin"
    MASTODON = "mastodon"
    WEBSITE = "website"
    EMAIL = "email"


class SocialLink(BaseModel):
    platform: SocialPlatform
    handle: str  # normalized handle (no @, no URL prefix)
    raw_value: str = ""  # original value as scraped


class IdentityLink(BaseModel):
    """Audit record for why two profiles were linked."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    key_type: str  # e.g. "github", "twitter", "email"
    key_value: str  # the normalized matching value
    confidence: float = 1.0  # always 1.0 — strict matching only
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_by: str = "identity_pipeline"


class PlatformProfile(BaseModel):
    """A researcher's profile on a single bug bounty platform."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    platform_name: str  # "hackerone", "bugcrowd", "intigriti"
    username: str
    display_name: str = ""
    bio: str = ""
    location: str = ""
    profile_url: str = ""
    social_links: list[SocialLink] = []
    badges: list[str] = []
    skill_tags: list[str] = []
    join_date: datetime | None = None
    last_active: datetime | None = None
    last_scraped: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProfileSnapshot(BaseModel):
    """Point-in-time metrics snapshot for velocity tracking."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    profile_id: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Core metrics
    overall_score: float | None = None
    global_rank: int | None = None
    total_earnings: float | None = None

    # Finding breakdown
    finding_count: int | None = None
    critical_count: int | None = None
    high_count: int | None = None
    medium_count: int | None = None
    low_count: int | None = None

    # Quality metrics
    signal_percentile: float | None = None
    impact_percentile: float | None = None
    acceptance_rate: float | None = None

    # Catch-all for platform-specific fields
    raw_data: dict = {}


class Researcher(BaseModel):
    """Canonical researcher entity linking profiles across platforms."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    canonical_name: str = ""  # best-guess display name
    profile_ids: list[str] = []
    identity_links: list[IdentityLink] = []
    composite_score: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
