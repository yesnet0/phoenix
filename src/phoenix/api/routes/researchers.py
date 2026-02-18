"""Researcher query and search endpoints."""

from fastapi import APIRouter, HTTPException

from phoenix.core.database import get_session
from phoenix.schema.queries import get_researcher_detail, list_researchers, search_profiles

router = APIRouter()


@router.get("/")
async def list_all(skip: int = 0, limit: int = 50):
    async with get_session() as session:
        researchers = await list_researchers(session, skip=skip, limit=limit)
    return {"researchers": researchers, "count": len(researchers)}


@router.get("/search/{username}")
async def search(username: str):
    async with get_session() as session:
        results = await search_profiles(session, username)
    return {"results": results, "count": len(results)}


@router.get("/{researcher_id}")
async def detail(researcher_id: str):
    async with get_session() as session:
        researcher = await get_researcher_detail(session, researcher_id)
    if not researcher:
        raise HTTPException(status_code=404, detail="Researcher not found")
    return researcher
