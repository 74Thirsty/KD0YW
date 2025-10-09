"""Plugin for ingesting Broadcastify public streams."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import httpx

from .base import StreamPlugin

LOGGER = logging.getLogger(__name__)


class BroadcastifyPlugin(StreamPlugin):
    plugin_id = "broadcastify"
    display_name = "Broadcastify Public Feed"
    legal_notice = (
        "Only for publicly listed Broadcastify streams. Respect feed provider terms."
    )
    capabilities = ["http", "metadata"]

    def __init__(self, *, stream_url: str, timeout: int = 10, chunk_size: int = 4096) -> None:
        super().__init__(stream_url=stream_url, timeout=timeout, chunk_size=chunk_size)
        self.stream_url = stream_url
        self.timeout = timeout
        self.chunk_size = chunk_size
        self._client: httpx.AsyncClient | None = None
        self._response: httpx.Response | None = None

    async def start(self) -> None:
        if self._client is not None:
            return
        LOGGER.info("Starting Broadcastify stream %s", self.stream_url)
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._response = await self._client.stream("GET", self.stream_url)
        await self._response.__aenter__()
        self._running = True

    async def stop(self) -> None:
        if self._client is None:
            return
        LOGGER.info("Stopping Broadcastify stream %s", self.stream_url)
        if self._response is not None:
            await self._response.aclose()
            self._response = None
        await self._client.aclose()
        self._client = None
        self._running = False

    def metadata(self) -> dict[str, str]:
        return {"stream_url": self.stream_url}

    async def stream_chunks(self) -> AsyncGenerator[bytes, None]:
        if self._response is None:
            raise RuntimeError("Plugin not started")
        async for chunk in self._response.aiter_bytes(self.chunk_size):
            yield chunk
