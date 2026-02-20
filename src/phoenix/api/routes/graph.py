"""Graph data endpoint for Sigma.js visualization."""

from fastapi import APIRouter
from phoenix.core.database import get_session
from phoenix.schema.queries import get_graph_data

router = APIRouter()


@router.get("/")
async def graph():
    """Return nodes and edges for the full researcher graph."""
    async with get_session() as session:
        data = await get_graph_data(session)
    return data
