"""Health check endpoint."""

from fastapi import APIRouter

from phoenix.core.database import verify_connectivity

router = APIRouter()


@router.get("/health")
async def health_check():
    neo4j_ok = await verify_connectivity()
    return {
        "status": "healthy" if neo4j_ok else "degraded",
        "neo4j": "connected" if neo4j_ok else "disconnected",
    }
