"""Scrape job tracking models."""

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class ScrapeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScrapeJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    platform_name: str
    status: ScrapeStatus = ScrapeStatus.PENDING
    max_profiles: int = 50
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class ScrapeResult(BaseModel):
    job_id: str
    profiles_scraped: int = 0
    profiles_failed: int = 0
    identities_resolved: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = []
