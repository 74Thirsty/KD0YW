"""Plugin discovery and lifecycle management."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any, Dict, Type

from .base import StreamPlugin

LOGGER = logging.getLogger(__name__)


class PluginRegistry:
    """Runtime registry for available plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, Type[StreamPlugin]] = {}
        self._disabled: set[str] = set()
        self._active_instances: dict[str, StreamPlugin] = {}
        self._lock = asyncio.Lock()

    def register(self, plugin_cls: Type[StreamPlugin]) -> None:
        LOGGER.info("Registering plugin %s", plugin_cls.plugin_id)
        if plugin_cls.plugin_id in self._plugins:
            raise ValueError(f"Plugin {plugin_cls.plugin_id} already registered")
        self._plugins[plugin_cls.plugin_id] = plugin_cls

    def list_plugins(self) -> list[dict[str, Any]]:
        data: list[dict[str, Any]] = []
        for plugin_id, cls in self._plugins.items():
            data.append(
                {
                    "plugin_id": plugin_id,
                    "display_name": cls.display_name,
                    "legal_notice": cls.legal_notice,
                    "capabilities": cls.capabilities,
                    "disabled": plugin_id in self._disabled,
                }
            )
        return data

    def disable(self, plugin_id: str) -> None:
        LOGGER.warning("Disabling plugin %s", plugin_id)
        self._disabled.add(plugin_id)

    def enable(self, plugin_id: str) -> None:
        LOGGER.info("Enabling plugin %s", plugin_id)
        self._disabled.discard(plugin_id)

    def is_disabled(self, plugin_id: str) -> bool:
        return plugin_id in self._disabled

    async def get_instance(self, plugin_id: str, **config: Any) -> StreamPlugin:
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin {plugin_id} is not registered")
        if plugin_id in self._disabled:
            raise PermissionError(f"Plugin {plugin_id} is disabled by admin policy")

        async with self._lock:
            if plugin_id in self._active_instances:
                LOGGER.debug("Reusing active instance for %s", plugin_id)
                return self._active_instances[plugin_id]

            plugin_cls = self._plugins[plugin_id]
            instance = plugin_cls(**config)
            await instance.start()
            self._active_instances[plugin_id] = instance
            LOGGER.info("Started plugin %s", plugin_id)
            return instance

    async def release_instance(self, plugin_id: str) -> None:
        async with self._lock:
            instance = self._active_instances.pop(plugin_id, None)
            if instance is not None:
                LOGGER.info("Stopping plugin %s", plugin_id)
                await instance.stop()

    async def stream(self, plugin_id: str, **config: Any) -> AsyncGenerator[bytes, None]:
        instance = await self.get_instance(plugin_id, **config)
        try:
            async for chunk in instance.stream_chunks():
                yield chunk
        finally:
            await self.release_instance(plugin_id)


registry = PluginRegistry()
