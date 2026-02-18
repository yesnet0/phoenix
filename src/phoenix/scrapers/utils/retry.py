"""Retry decorators using tenacity."""

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from phoenix.config import settings


def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient errors worth retrying.

    Covers:
    - httpx transport errors (ConnectError, ConnectTimeout, ReadTimeout, etc.)
    - httpx HTTP 429 / 5xx status errors (server-side, not client mistakes)
    - stdlib socket / OS-level errors
    """
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    if isinstance(exc, (httpx.TransportError, TimeoutError, ConnectionError, OSError)):
        return True
    return False


# Retry on common transient HTTP errors
scrape_retry = retry(
    stop=stop_after_attempt(settings.scrape_max_retries),
    wait=wait_exponential_jitter(initial=2, max=60, jitter=2),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)
