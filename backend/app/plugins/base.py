"""Plugin contracts for ScannerForge stream sources."""
from __future__ import annotations

import abc
from collections.abc import AsyncGenerator
from typing import Any


class StreamPlugin(abc.ABC):
    """Base class that all stream plugins must implement."""

    plugin_id: str
    display_name: str
    legal_notice: str
    capabilities: list[str]

    def __init__(self, **config: Any) -> None:
        self.config = config
        self._running = False

    async def __aenter__(self) -> "StreamPlugin":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.stop()

    @abc.abstractmethod
    async def start(self) -> None:
        """Initialize network/file handles. Should be idempotent."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Release any resources allocated by :meth:`start`."""

    @abc.abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Return plugin specific metadata to present on the frontend."""

    @abc.abstractmethod
    async def stream_chunks(self) -> AsyncGenerator[bytes, None]:
        """Yield audio chunks as raw bytes (prefer Opus encoded)."""
