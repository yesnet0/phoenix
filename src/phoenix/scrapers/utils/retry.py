"""Retry decorators using tenacity."""

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from phoenix.config import settings

# Retry on common transient HTTP errors
scrape_retry = retry(
    stop=stop_after_attempt(settings.scrape_max_retries),
    wait=wait_exponential_jitter(initial=2, max=60, jitter=2),
    retry=retry_if_exception_type((TimeoutError, ConnectionError, OSError)),
    reraise=True,
)
