import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting a scraper source."""
    requests_per_minute: int = 10
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 10.0
    jitter: bool = True


RATE_LIMITS: Dict[str, RateLimitConfig] = {
    'running_warehouse': RateLimitConfig(
        requests_per_minute=10,
        min_delay_seconds=6.0,
        max_delay_seconds=12.0,
    ),
    'doctors_of_running': RateLimitConfig(
        requests_per_minute=6,
        min_delay_seconds=10.0,
        max_delay_seconds=20.0,
    ),
    'believe_in_the_run': RateLimitConfig(
        requests_per_minute=10,
        min_delay_seconds=6.0,
        max_delay_seconds=12.0,
    ),
    'weartesters': RateLimitConfig(
        requests_per_minute=3,
        min_delay_seconds=20.0,
        max_delay_seconds=40.0,
    ),
    'fleet_feet': RateLimitConfig(
        requests_per_minute=5,
        min_delay_seconds=12.0,
        max_delay_seconds=24.0,
    ),
    'road_runner_sports': RateLimitConfig(
        requests_per_minute=5,
        min_delay_seconds=12.0,
        max_delay_seconds=24.0,
    ),
}


@dataclass
class RateLimiter:
    """Rate limiter for scraper requests."""
    source: str
    config: RateLimitConfig = field(init=False)
    last_request_time: float = field(default=0.0, init=False)

    def __post_init__(self):
        self.config = RATE_LIMITS.get(self.source, RateLimitConfig())

    def _calculate_delay(self) -> float:
        """Calculate delay with optional jitter."""
        base_delay = self.config.min_delay_seconds

        if self.config.jitter:
            jitter_range = self.config.max_delay_seconds - self.config.min_delay_seconds
            base_delay += random.random() * jitter_range

        return base_delay

    async def wait(self) -> None:
        """Wait appropriate time before next request."""
        now = time.time()
        elapsed = now - self.last_request_time
        delay = self._calculate_delay()

        if elapsed < delay:
            wait_time = delay - elapsed
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()

    def wait_sync(self) -> None:
        """Synchronous version of wait for non-async scrapers."""
        now = time.time()
        elapsed = now - self.last_request_time
        delay = self._calculate_delay()

        if elapsed < delay:
            wait_time = delay - elapsed
            time.sleep(wait_time)

        self.last_request_time = time.time()
