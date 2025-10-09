"""Plugin for streaming audio from a local file."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import aiofiles

from .base import StreamPlugin

LOGGER = logging.getLogger(__name__)


class LocalFilePlugin(StreamPlugin):
    plugin_id = "local_file"
    display_name = "Local File"
    legal_notice = "Only stream files that you are authorized to use."
    capabilities = ["file", "metadata"]

    def __init__(self, *, path: str, chunk_size: int = 4096, throttle: float | None = None) -> None:
        super().__init__(path=path, chunk_size=chunk_size, throttle=throttle)
        self.path = Path(path)
        self.chunk_size = chunk_size
        self.throttle = throttle
        self._validate_path()

    def _validate_path(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        if not self.path.is_file():
            raise ValueError(f"{self.path} is not a file")

    async def start(self) -> None:
        LOGGER.info("Preparing local file %s", self.path)
        self._running = True

    async def stop(self) -> None:
        LOGGER.info("Local file stream stopped %s", self.path)
        self._running = False

    def metadata(self) -> dict[str, str]:
        return {"path": str(self.path), "size": str(self.path.stat().st_size)}

    async def stream_chunks(self) -> AsyncGenerator[bytes, None]:
        async with aiofiles.open(self.path, "rb") as handle:
            chunk = await handle.read(self.chunk_size)
            while chunk:
                yield chunk
                if self.throttle:
                    await asyncio.sleep(self.throttle)
                chunk = await handle.read(self.chunk_size)
