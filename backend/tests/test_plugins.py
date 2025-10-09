"""Unit tests for plugin registry and base contract."""
import asyncio
from pathlib import Path

import pytest

from app.plugins.base import StreamPlugin
from app.plugins import manager


class DummyPlugin(StreamPlugin):
    plugin_id = "dummy"
    display_name = "Dummy"
    legal_notice = ""
    capabilities = ["test"]

    def __init__(self) -> None:
        super().__init__()
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    def metadata(self) -> dict[str, str]:
        return {"hello": "world"}

    async def stream_chunks(self):  # type: ignore[override]
        yield b"test"


@pytest.mark.asyncio
async def test_registry_register_and_stream(tmp_path: Path):
    registry = manager.PluginRegistry()
    registry.register(DummyPlugin)

    instance = await registry.get_instance("dummy")
    assert isinstance(instance, DummyPlugin)
    assert instance.started

    chunks = []
    async for chunk in registry.stream("dummy"):
        chunks.append(chunk)
        break
    assert chunks == [b"test"]

    await registry.release_instance("dummy")
    assert not instance.started


@pytest.mark.asyncio
async def test_disable_plugin():
    registry = manager.PluginRegistry()
    registry.register(DummyPlugin)
    registry.disable("dummy")

    with pytest.raises(PermissionError):
        await registry.get_instance("dummy")
