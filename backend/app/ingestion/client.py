"""The only module that talks to stats.nba.com.

nba_api builds request parameters and parses responses; this client owns the HTTP call itself so it
can classify failures, honor Retry-After, throttle, and cache completed-season responses on disk.
"""

import hashlib
import json
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
import requests
from nba_api.stats.library.http import NBAStatsHTTP, NBAStatsResponse

from app.config import get_settings

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class StatsSourceError(Exception):
    retryable = False


class RetryableSourceError(StatsSourceError):
    retryable = True

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class NonRetryableSourceError(StatsSourceError):
    pass


class UnexpectedResponseError(NonRetryableSourceError):
    """The source answered, but not with the tables this endpoint should have."""


@dataclass
class FetchResult:
    frames: list[pd.DataFrame]
    attempts: int
    from_cache: bool = False


class StatsSource(Protocol):
    def fetch(
        self, endpoint_cls: type, *, cacheable: bool = False, **params: Any
    ) -> FetchResult: ...


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError):
        return None


def backoff_delay(attempt: int, base: float, cap: float, rng: random.Random) -> float:
    """Full-jitter exponential backoff: uniform(0, min(cap, base * 2**(attempt-1)))."""
    return rng.uniform(0, min(cap, base * 2 ** (attempt - 1)))


@dataclass
class NBAStatsClient:
    interval: float = field(default_factory=lambda: get_settings().stats_request_interval_seconds)
    timeout: float = field(default_factory=lambda: get_settings().stats_timeout_seconds)
    max_attempts: int = field(default_factory=lambda: get_settings().stats_max_attempts)
    backoff_base: float = field(default_factory=lambda: get_settings().stats_backoff_base_seconds)
    backoff_cap: float = field(default_factory=lambda: get_settings().stats_backoff_cap_seconds)
    cache_dir: Path = field(default_factory=lambda: get_settings().stats_cache_dir)
    session: requests.Session = field(default_factory=requests.Session)
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    rng: random.Random = field(default_factory=random.Random)
    _last_request: float | None = None

    def fetch(self, endpoint_cls: type, *, cacheable: bool = False, **params: Any) -> FetchResult:
        endpoint = endpoint_cls(get_request=False, **params)
        url = NBAStatsHTTP.base_url.format(endpoint=endpoint.endpoint)
        query = dict(sorted(endpoint.parameters.items()))
        cache_path = self._cache_path(endpoint.endpoint, query) if cacheable else None

        if cache_path and cache_path.exists():
            body, attempts, from_cache = cache_path.read_text(), 0, True
        else:
            body, attempts = self._request_with_retries(url, query)
            from_cache = False

        endpoint.nba_response = NBAStatsResponse(response=body, status_code=200, url=url)
        try:
            endpoint.load_response()
            frames = endpoint.get_data_frames()
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            if cache_path and from_cache:
                cache_path.unlink(missing_ok=True)
            raise UnexpectedResponseError(
                f"{endpoint.endpoint}: response did not match the expected schema ({exc})"
            ) from exc

        if cache_path and not from_cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(body)
        return FetchResult(frames=frames, attempts=attempts, from_cache=from_cache)

    def _request_with_retries(self, url: str, query: dict[str, Any]) -> tuple[str, int]:
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self._request_once(url, query), attempt
            except RetryableSourceError as exc:
                if attempt == self.max_attempts:
                    raise
                delay = backoff_delay(attempt, self.backoff_base, self.backoff_cap, self.rng)
                if exc.retry_after is not None:
                    delay = max(delay, min(exc.retry_after, self.backoff_cap))
                log.warning(
                    "stats request retry",
                    extra={"url": url, "attempt": attempt, "delay_s": round(delay, 2),
                           "reason": str(exc)},
                )  # fmt: skip
                self.sleep(delay)
        raise AssertionError("unreachable")

    def _request_once(self, url: str, query: dict[str, Any]) -> str:
        self._throttle()
        try:
            response = self.session.get(
                url, params=query, headers=NBAStatsHTTP.headers, timeout=self.timeout
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise RetryableSourceError(type(exc).__name__) from exc
        except requests.RequestException as exc:
            raise NonRetryableSourceError(type(exc).__name__) from exc

        if response.status_code in RETRYABLE_STATUS:
            raise RetryableSourceError(
                f"HTTP {response.status_code}",
                retry_after=parse_retry_after(response.headers.get("Retry-After")),
            )
        if response.status_code != 200:
            raise NonRetryableSourceError(f"HTTP {response.status_code}")
        try:
            json.loads(response.text)
        except ValueError as exc:
            raise RetryableSourceError("Response body was not JSON") from exc
        return response.text

    def _throttle(self) -> None:
        now = self.clock()
        if self._last_request is not None:
            wait = self.interval - (now - self._last_request)
            if wait > 0:
                self.sleep(wait)
        self._last_request = self.clock()

    def _cache_path(self, endpoint: str, query: dict[str, Any]) -> Path:
        digest = hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest()[:24]
        return self.cache_dir / endpoint / f"{digest}.json"
