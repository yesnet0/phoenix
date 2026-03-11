"""Analytics dashboard endpoint."""

from fastapi import APIRouter
from phoenix.core.database import get_session
from phoenix.schema.queries import (
    get_analytics,
    get_activity_heatmap,
    get_cross_platform_overlap,
    get_finding_velocity,
    get_platform_affinity,
    get_platform_comparison,
    get_researchers_by_skill,
    get_rising_stars,
    get_skill_distribution,
    recompute_composite_scores,
)
from phoenix.skills.taxonomy import run_skill_inference

router = APIRouter()


@router.get("")
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


@router.get("/skills")
async def skills(skill: str | None = None, skip: int = 0, limit: int = 50):
    """Skill distribution or researchers filtered by skill."""
    async with get_session() as session:
        if skill:
            researchers = await get_researchers_by_skill(session, skill, skip=skip, limit=limit)
            return {"skill": skill, "researchers": researchers, "count": len(researchers)}
        distribution = await get_skill_distribution(session)
    return {"distribution": distribution}


@router.post("/skills/infer")
async def infer_skills():
    """Run the skill inference pipeline."""
    async with get_session() as session:
        result = await run_skill_inference(session)
    return result


@router.get("/rising-stars")
async def rising_stars(limit: int = 10):
    """Top researchers by score growth velocity."""
    async with get_session() as session:
        data = await get_rising_stars(session, limit=limit)
    return {"rising_stars": data}


@router.get("/heatmap")
async def heatmap():
    """Activity timeline — profiles grouped by join month."""
    async with get_session() as session:
        data = await get_activity_heatmap(session)
    return {"heatmap": data}


@router.get("/finding-velocity")
async def finding_velocity(limit: int = 10):
    """Top researchers by finding velocity."""
    async with get_session() as session:
        data = await get_finding_velocity(session, limit=limit)
    return {"velocity": data}


@router.get("/platform-comparison")
async def platform_comparison():
    """Average score, findings, earnings per platform."""
    async with get_session() as session:
        data = await get_platform_comparison(session)
    return {"platforms": data}


@router.get("/cross-platform")
async def cross_platform():
    """Cross-platform overlap and affinity."""
    async with get_session() as session:
        overlap = await get_cross_platform_overlap(session)
        affinity = await get_platform_affinity(session)
    return {"overlap": overlap, "affinity": affinity}
