"""Human-like timing utilities."""

import asyncio
import random

from phoenix.config import settings


async def jittered_delay(
    min_seconds: float | None = None,
    max_seconds: float | None = None,
) -> None:
    """Sleep for a random duration to mimic human browsing patterns."""
    lo = min_seconds or settings.scrape_delay_min
    hi = max_seconds or settings.scrape_delay_max
    delay = random.uniform(lo, hi)
    await asyncio.sleep(delay)


async def exponential_backoff(attempt: int, base: float = 1.0, max_delay: float = 60.0) -> None:
    """Exponential backoff with jitter."""
    delay = min(base * (2**attempt) + random.uniform(0, 1), max_delay)
    await asyncio.sleep(delay)
