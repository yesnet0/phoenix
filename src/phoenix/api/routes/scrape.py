"""Scrape trigger and status endpoints + Celery task."""

import asyncio
import time
from datetime import datetime, UTC

from celery import shared_task
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from phoenix.core.database import get_session
from phoenix.core.logging import get_logger
from phoenix.core.tasks import app as celery_app
from phoenix.identity.resolver import resolve_batch
from phoenix.models.scrape import ScrapeResult, ScrapeStatus
from phoenix.schema.queries import create_snapshot, upsert_profile
from phoenix.scrapers.registry import discover_scrapers, get_scraper, list_scrapers

# Auto-discover all scrapers when this module is imported (including by Celery workers)
discover_scrapers()

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


@router.post("/health")
async def scrape_health():
    """Quick health check: try to instantiate each scraper and fetch its leaderboard with max_entries=1."""
    results = {}

    async def check_platform(name: str) -> dict:
        try:
            scraper = get_scraper(name)
            try:
                entries = await asyncio.wait_for(
                    scraper.scrape_leaderboard(max_entries=1),
                    timeout=30.0,
                )
                return {
                    "status": "ok" if entries else "empty",
                    "entries": len(entries),
                    "checked_at": datetime.now(UTC).isoformat(),
                }
            except asyncio.TimeoutError:
                return {"status": "timeout", "checked_at": datetime.now(UTC).isoformat()}
            except Exception as e:
                error_msg = str(e)
                status = "captcha" if "captcha" in error_msg.lower() else "error"
                return {"status": status, "error": error_msg, "checked_at": datetime.now(UTC).isoformat()}
            finally:
                await scraper.close()
        except Exception as e:
            return {"status": "error", "error": str(e), "checked_at": datetime.now(UTC).isoformat()}

    # Run checks sequentially to avoid overwhelming resources
    for name in list_scrapers():
        results[name] = await check_platform(name)

    ok_count = sum(1 for r in results.values() if r["status"] == "ok")
    return {
        "total": len(results),
        "ok": ok_count,
        "failing": len(results) - ok_count,
        "platforms": results,
    }


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
