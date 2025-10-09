"""Audio helpers for transcoding and recording."""
from __future__ import annotations

import asyncio
import logging
import contextlib
from collections.abc import AsyncGenerator
from pathlib import Path

from .plugins.base import StreamPlugin

LOGGER = logging.getLogger(__name__)


async def _spawn_ffmpeg(*args: str, stdout_pipe: bool = True, stderr_pipe: bool = True):
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE if stdout_pipe else None,
        stderr=asyncio.subprocess.PIPE if stderr_pipe else None,
    )
    return process


async def _feed_process(stdin, stream: AsyncGenerator[bytes, None]) -> None:
    try:
        async for chunk in stream:
            if stdin.is_closing():
                break
            stdin.write(chunk)
            await stdin.drain()
    except asyncio.CancelledError:
        LOGGER.debug("Feed task cancelled")
        raise
    finally:
        try:
            stdin.close()
        except Exception:  # pragma: no cover - best effort cleanup
            LOGGER.exception("Failed to close ffmpeg stdin")


async def transcode_to_opus(plugin: StreamPlugin) -> AsyncGenerator[bytes, None]:
    """Convert plugin audio output to Opus chunks using ffmpeg."""

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-i",
        "pipe:0",
        "-c:a",
        "libopus",
        "-f",
        "ogg",
        "pipe:1",
    ]
    process = await _spawn_ffmpeg(*cmd)
    assert process.stdout is not None
    assert process.stdin is not None

    feed_task = asyncio.create_task(_feed_process(process.stdin, plugin.stream_chunks()))
    try:
        while True:
            chunk = await process.stdout.read(4096)
            if not chunk:
                if process.returncode is not None:
                    break
                await asyncio.sleep(0.1)
                continue
            yield chunk
    finally:
        feed_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await feed_task
        process.kill()
        await process.wait()


async def record_opus(
    plugin: StreamPlugin,
    destination: Path,
    duration_seconds: int = 30,
) -> Path:
    """Record an Opus clip from a plugin using ffmpeg."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-loglevel",
        "warning",
        "-i",
        "pipe:0",
        "-t",
        str(duration_seconds),
        "-c:a",
        "libopus",
        "-f",
        "ogg",
        str(destination),
    ]
    process = await _spawn_ffmpeg(*cmd, stdout_pipe=False)
    assert process.stdin is not None
    feed_task = asyncio.create_task(_feed_process(process.stdin, plugin.stream_chunks()))
    await process.wait()
    feed_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await feed_task

    LOGGER.info("Recorded clip to %s", destination)
    return destination
