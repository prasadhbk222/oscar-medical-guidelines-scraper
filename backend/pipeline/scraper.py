"""Polite async HTTP: bounded concurrency, min-interval throttle, retry+backoff."""

from __future__ import annotations

import asyncio
import logging

import httpx

log = logging.getLogger("scraper")

USER_AGENT = "OscarGuidelineScraper/0.1 (+take-home; contact via repo)"


class PoliteClient:
    def __init__(
        self,
        concurrency: int = 5,
        min_interval: float = 0.15,
        retries: int = 3,
        timeout: float = 30.0,
    ):
        self._sem = asyncio.Semaphore(concurrency)
        self._min_interval = min_interval
        self._retries = retries
        self._lock = asyncio.Lock()
        self._next_at = 0.0
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )

    async def __aenter__(self) -> "PoliteClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.aclose()

    async def _throttle(self) -> None:
        # Serialize the gate so requests are spaced by >= min_interval.
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait = self._next_at - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next_at = asyncio.get_event_loop().time() + self._min_interval

    async def get(self, url: str) -> httpx.Response:
        """GET with throttle + retry. Raises on final failure."""
        last_exc: Exception | None = None
        for attempt in range(1, self._retries + 1):
            async with self._sem:
                await self._throttle()
                try:
                    resp = await self._client.get(url)
                    if resp.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"server {resp.status_code}",
                            request=resp.request,
                            response=resp,
                        )
                    return resp
                except (httpx.TransportError, httpx.HTTPStatusError) as e:
                    last_exc = e
                    backoff = 0.5 * (2 ** (attempt - 1))
                    log.warning(
                        "GET %s failed (attempt %d/%d): %s; retrying in %.1fs",
                        url, attempt, self._retries, e, backoff,
                    )
                    await asyncio.sleep(backoff)
        assert last_exc is not None
        raise last_exc
