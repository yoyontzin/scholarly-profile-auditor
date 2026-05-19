"""BaseConnector: httpx async + rate-limit por dominio + retries con backoff.

Diseño: cada conector concreto instancia un cliente httpx compartido a través
de get_client(); el rate-limiter es por host (no global) porque los proveedores
imponen límites independientes.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar
from urllib.parse import urlparse

import httpx
from aiolimiter import AsyncLimiter
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectorError(Exception):
    """Error de conector recuperable o no según el subtipo."""


class RetryableError(ConnectorError):
    """5xx, 429, timeouts."""


class FatalError(ConnectorError):
    """4xx no recuperables o parse errors."""


class BaseConnector:
    """Cliente HTTP con rate-limit por host, retries y User-Agent identificable.

    Subclases definen `default_base_url` y métodos específicos. Usan
    `await self.get_json(url, params=...)` que ya gestiona todo.
    """

    default_base_url: ClassVar[str] = ""
    _limiters: ClassVar[dict[str, AsyncLimiter]] = {}
    _client: ClassVar[httpx.AsyncClient | None] = None

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.cfg = get_config()

    # ------------------------------------------------------------------
    # Cliente compartido
    # ------------------------------------------------------------------
    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        if cls._client is None or cls._client.is_closed:
            cfg = get_config()
            timeout = float(cfg.http().get("timeout_seconds", cfg.env.http_timeout))
            ua = (
                f"scholarly-profile-auditor/0.1 "
                f"(mailto:{cfg.env.user_email}; +https://github.com/example/spa)"
            )
            cls._client = httpx.AsyncClient(
                timeout=timeout,
                headers={"User-Agent": ua, "Accept": "application/json"},
                follow_redirects=True,
            )
        return cls._client

    @classmethod
    async def close_client(cls) -> None:
        if cls._client and not cls._client.is_closed:
            await cls._client.aclose()
        cls._client = None

    # ------------------------------------------------------------------
    # Rate limiter por host
    # ------------------------------------------------------------------
    def _limiter_for(self, url: str) -> AsyncLimiter:
        host = urlparse(url).netloc.lower()
        if host not in self._limiters:
            cfg_limits = self.cfg.rate_limits()
            rate = float(cfg_limits.get(host, 5.0))  # default 5 req/s
            # AsyncLimiter(max_rate, time_period) — usamos 1s
            self._limiters[host] = AsyncLimiter(max_rate=rate, time_period=1.0)
        return self._limiters[host]

    # ------------------------------------------------------------------
    # GET con todo el cinturón de seguridad
    # ------------------------------------------------------------------
    async def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        client = await self.get_client()
        limiter = self._limiter_for(url)
        http_cfg = self.cfg.http()
        retries = int(http_cfg.get("retries", 3))
        backoff_initial = float(http_cfg.get("backoff_initial", 0.5))
        backoff_max = float(http_cfg.get("backoff_max", 8.0))

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(retries),
            wait=wait_exponential(multiplier=backoff_initial, max=backoff_max),
            retry=retry_if_exception_type((RetryableError, httpx.TransportError)),
            reraise=True,
        ):
            with attempt:
                async with limiter:
                    logger.debug("GET %s params=%s", url, params)
                    resp = await client.get(url, params=params, headers=headers)
                    if resp.status_code in (429, 500, 502, 503, 504):
                        # respetar Retry-After si viene
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                await asyncio.sleep(float(retry_after))
                            except ValueError:
                                pass
                        raise RetryableError(f"{url} → {resp.status_code}")
                    if resp.status_code >= 400:
                        raise FatalError(
                            f"{url} → {resp.status_code}: {resp.text[:200]}"
                        )
                    try:
                        return resp.json()
                    except ValueError as e:
                        raise FatalError(f"JSON parse error from {url}: {e}") from e

        # unreachable
        raise FatalError("Unreachable retry path")
