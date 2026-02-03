import logging
from typing import Tuple, Type

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.ConnectError,
    httpx.ReadError,
)


def create_retry_decorator(max_attempts: int = 3, min_wait: int = 4, max_wait: int = 60):
    """
    Create a retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time in seconds between retries
        max_wait: Maximum wait time in seconds between retries
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def should_retry_status(status_code: int) -> bool:
    """Check if an HTTP status code should trigger a retry."""
    return status_code in (429, 500, 502, 503, 504)
