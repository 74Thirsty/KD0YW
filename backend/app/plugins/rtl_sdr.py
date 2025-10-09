"""RTL-SDR plugin constrained to legal amateur/weather bands."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
import os
from pathlib import Path
from typing import Any

from .base import StreamPlugin

LOGGER = logging.getLogger(__name__)


class RTLSDRPlugin(StreamPlugin):
    plugin_id = "rtl_sdr"
    display_name = "RTL-SDR (Legal Bands Only)"
    legal_notice = (
        "Operate only on unencrypted amateur, NOAA weather, or other public bands. "
        "Do NOT attempt to monitor trunked or encrypted systems."
    )
    capabilities = ["sdr", "iq", "warning"]

    def __init__(
        self,
        *,
        center_frequency: float,
        sample_rate: int = 1_000_000,
        gain: int | None = None,
        device_index: int = 0,
        ffmpeg_path: str = "ffmpeg",
    ) -> None:
        super().__init__(
            center_frequency=center_frequency,
            sample_rate=sample_rate,
            gain=gain,
            device_index=device_index,
            ffmpeg_path=ffmpeg_path,
        )
        if center_frequency < 100e6:
            raise ValueError("Center frequency must be >= 100 MHz (weather/ham bands)")
        self.center_frequency = center_frequency
        self.sample_rate = sample_rate
        self.gain = gain
        self.device_index = device_index
        self.ffmpeg_path = ffmpeg_path
        self._process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        if self._process is not None:
            return
        LOGGER.info(
            "Starting RTL-SDR capture @ %.2f MHz", self.center_frequency / 1e6
        )
        cmd = [
            self.ffmpeg_path,
            "-hide_banner",
            "-nostats",
            "-f",
            "s16le",
            "-sample_rate",
            str(self.sample_rate),
            "-channels",
            "1",
            "-i",
            f"rtl+{self.device_index}",
            "-filter:a",
            "aresample=48000",
            "-c:a",
            "libopus",
            "-f",
            "opus",
            "pipe:1",
        ]
        env = {
            **os.environ,
            "RTLSDR_CENTER_FREQ": str(self.center_frequency),
            "RTLSDR_GAIN": "auto" if self.gain is None else str(self.gain),
        }
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._running = True

    async def stop(self) -> None:
        if self._process is None:
            return
        LOGGER.info("Stopping RTL-SDR capture")
        self._process.terminate()
        await self._process.wait()
        self._process = None
        self._running = False

    def metadata(self) -> dict[str, Any]:
        return {
            "center_frequency": self.center_frequency,
            "sample_rate": self.sample_rate,
            "gain": self.gain,
        }

    async def stream_chunks(self) -> AsyncGenerator[bytes, None]:
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("Plugin not started")
        while True:
            chunk = await self._process.stdout.read(4096)
            if not chunk:
                break
            yield chunk
