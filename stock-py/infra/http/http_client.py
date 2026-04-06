from __future__ import annotations

from functools import lru_cache

import httpx

from infra.core.config import get_settings


class HttpClientFactory:
    def __init__(self, timeout_seconds: float | None = None) -> None:
        settings = get_settings()
        self.timeout_seconds = timeout_seconds or settings.http_timeout_seconds
        self._internal_client: httpx.AsyncClient | None = None
        self._external_client: httpx.AsyncClient | None = None

    async def get_internal_client(self) -> httpx.AsyncClient:
        if self._internal_client is None:
            self._internal_client = httpx.AsyncClient(
                timeout=self.timeout_seconds,
                headers={"User-Agent": "stock-py/internal"},
            )
        return self._internal_client

    async def get_external_client(self) -> httpx.AsyncClient:
        if self._external_client is None:
            self._external_client = httpx.AsyncClient(
                timeout=self.timeout_seconds,
                headers={"User-Agent": "stock-py/external"},
                follow_redirects=True,
            )
        return self._external_client

    async def aclose(self) -> None:
        if self._internal_client is not None:
            await self._internal_client.aclose()
            self._internal_client = None
        if self._external_client is not None:
            await self._external_client.aclose()
            self._external_client = None


@lru_cache(maxsize=1)
def get_http_client_factory() -> HttpClientFactory:
    return HttpClientFactory()
