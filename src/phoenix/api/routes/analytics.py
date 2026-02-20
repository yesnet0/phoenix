"""Analytics dashboard endpoint."""

from fastapi import APIRouter
from phoenix.core.database import get_session
from phoenix.schema.queries import get_analytics

router = APIRouter()


@router.get("/")
async def analytics():
    """Return aggregated dashboard statistics."""
    async with get_session() as session:
        data = await get_analytics(session)
    return data
