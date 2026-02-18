"""Scrape trigger and status endpoints + Celery task."""

import time
from datetime import datetime

from celery import shared_task
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from phoenix.core.database import get_session
from phoenix.core.logging import get_logger
from phoenix.core.tasks import app as celery_app
from phoenix.identity.resolver import resolve_batch
from phoenix.models.scrape import ScrapeResult, ScrapeStatus
from phoenix.schema.queries import create_snapshot, upsert_profile
from phoenix.scrapers.registry import get_scraper, list_scrapers

# Ensure scrapers are registered when this module is imported (including by Celery workers)
import phoenix.scrapers.hackerone  # noqa: F401
import phoenix.scrapers.bugcrowd  # noqa: F401
import phoenix.scrapers.intigriti  # noqa: F401

log = get_logger(__name__)
router = APIRouter()


class TriggerRequest(BaseModel):
    platform_name: str
    max_profiles: int = 50


class TriggerResponse(BaseModel):
    job_id: str
    status: str


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_scrape(req: TriggerRequest):
    if req.platform_name not in list_scrapers():
        raise HTTPException(status_code=400, detail=f"Unknown platform: {req.platform_name}")

    result = run_scrape.delay(req.platform_name, req.max_profiles)
    return TriggerResponse(job_id=result.id, status="queued")


@router.get("/status/{job_id}")
async def scrape_status(job_id: str):
    result = celery_app.AsyncResult(job_id)
    response = {
        "job_id": job_id,
        "status": result.status,
    }
    if result.ready():
        response["result"] = result.result
    return response


@router.get("/platforms")
async def platforms():
    return {"platforms": list_scrapers()}


@shared_task(name="phoenix.scrape", bind=True)
def run_scrape(self, platform_name: str, max_profiles: int = 50) -> dict:
    """Celery task: scrape platform → store in Neo4j → resolve identities."""
    import asyncio

    return asyncio.run(_run_scrape_async(self.request.id, platform_name, max_profiles))


async def _run_scrape_async(job_id: str, platform_name: str, max_profiles: int) -> dict:
    # Reset Neo4j driver to bind to current event loop (Celery creates fresh loops per asyncio.run)
    from phoenix.core.database import reset_driver
    await reset_driver()

    start = time.time()
    scraper = get_scraper(platform_name)
    errors: list[str] = []
    profiles_scraped = 0
    profiles_failed = 0
    identities_resolved = 0

    try:
        results = await scraper.scrape_full(max_profiles=max_profiles)

        async with get_session() as session:
            stored_profiles = []
            for profile, snapshot in results:
                try:
                    profile_id = await upsert_profile(session, profile)
                    snapshot.profile_id = profile_id
                    await create_snapshot(session, snapshot)
                    stored_profiles.append(profile)
                    profiles_scraped += 1
                except Exception as e:
                    profiles_failed += 1
                    errors.append(f"{profile.username}: {e}")

            # Run identity resolution
            identities_resolved = await resolve_batch(session, stored_profiles)

    except Exception as e:
        errors.append(str(e))
        log.error("scrape_failed", platform=platform_name, error=str(e))
    finally:
        await scraper.close()

    result = ScrapeResult(
        job_id=job_id,
        profiles_scraped=profiles_scraped,
        profiles_failed=profiles_failed,
        identities_resolved=identities_resolved,
        duration_seconds=round(time.time() - start, 2),
        errors=errors,
    )
    return result.model_dump()
