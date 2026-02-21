"""Researcher query and search endpoints."""

from fastapi import APIRouter, HTTPException

from phoenix.core.database import get_session
from phoenix.schema.queries import (
    get_identity_links,
    get_researcher_count,
    get_researcher_detail,
    list_profiles,
    list_researchers,
    list_researchers_enriched,
    get_available_platforms,
    search_profiles,
)

router = APIRouter()


@router.get("/")
async def list_all(skip: int = 0, limit: int = 50, sort: str = "score"):
    async with get_session() as session:
        researchers = await list_researchers_enriched(session, skip=skip, limit=limit, sort_by=sort)
        total = await get_researcher_count(session)
    return {"researchers": researchers, "total": total, "count": len(researchers)}


@router.get("/search/{username}")
async def search(username: str):
    async with get_session() as session:
        results = await search_profiles(session, username)
    return {"results": results, "count": len(results)}


@router.get("/profiles")
async def profiles(skip: int = 0, limit: int = 50, platform: str | None = None, sort: str = "earnings"):
    async with get_session() as session:
        results = await list_profiles(session, skip=skip, limit=limit, platform=platform, sort_by=sort)
        platforms = await get_available_platforms(session)
    return {"profiles": results, "count": len(results), "platforms": platforms}


@router.get("/{researcher_id}")
async def detail(researcher_id: str):
    async with get_session() as session:
        researcher = await get_researcher_detail(session, researcher_id)
        if not researcher:
            raise HTTPException(status_code=404, detail="Researcher not found")
        links = await get_identity_links(session, researcher_id)
    researcher["identity_links"] = links
    return researcher
