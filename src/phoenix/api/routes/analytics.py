"""Analytics dashboard endpoint."""

from fastapi import APIRouter
from phoenix.core.database import get_session
from phoenix.schema.queries import get_analytics, recompute_composite_scores

router = APIRouter()


@router.get("/")
async def analytics():
    """Return aggregated dashboard statistics."""
    async with get_session() as session:
        data = await get_analytics(session)
    return data


@router.post("/recompute-scores")
async def recompute_scores():
    """Recompute composite scores for all researchers."""
    async with get_session() as session:
        updated = await recompute_composite_scores(session)
    return {"updated": updated}
