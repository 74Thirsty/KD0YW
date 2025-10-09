"""FastAPI application entrypoint for ScannerForge."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import config
from .audio import record_opus, transcode_to_opus
from .plugins import broadcastify, local_file, manager, rtl_sdr
from .plugins.base import StreamPlugin

LOGGER = logging.getLogger(__name__)

class StreamRequest(BaseModel):
    """Request body for stream operations."""

    config: dict[str, Any] = {}
    duration: int | None = None


def _coerce_value(value: str) -> Any:
    for caster in (int, float):
        try:
            return caster(value)
        except ValueError:
            continue
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    return value

logging.basicConfig(level=logging.INFO)

app = FastAPI(title=config.settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.on_event("startup")
async def startup() -> None:
    LOGGER.info("Starting ScannerForge backend")
    for plugin in (broadcastify.BroadcastifyPlugin, local_file.LocalFilePlugin, rtl_sdr.RTLSDRPlugin):
        try:
            manager.registry.register(plugin)
        except ValueError:
            LOGGER.debug("Plugin %s already registered", plugin.plugin_id)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/plugins")
async def list_plugins() -> list[dict[str, object]]:
    return manager.registry.list_plugins()


@app.post("/admin/plugins/{plugin_id}/disable")
async def disable_plugin(plugin_id: str) -> JSONResponse:
    manager.registry.disable(plugin_id)
    return JSONResponse({"plugin_id": plugin_id, "disabled": True})


@app.post("/admin/plugins/{plugin_id}/enable")
async def enable_plugin(plugin_id: str) -> JSONResponse:
    manager.registry.enable(plugin_id)
    return JSONResponse({"plugin_id": plugin_id, "disabled": False})


async def get_plugin_instance(
    plugin_id: str,
    config_override: dict[str, Any] | None = None,
    request_like: Any | None = None,
) -> StreamPlugin:
    config_data: dict[str, Any] = {}
    if request_like is not None and hasattr(request_like, "query_params"):
        config_data.update(
            {k: _coerce_value(v) for k, v in dict(request_like.query_params).items()}
        )
    if config_override:
        config_data.update(config_override)
    try:
        return await manager.registry.get_instance(plugin_id, **config_data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/streams/{plugin_id}/metadata")
async def stream_metadata(plugin_id: str, request: Request) -> dict[str, object]:
    plugin = await get_plugin_instance(plugin_id, request_like=request)
    try:
        return plugin.metadata()
    finally:
        await manager.registry.release_instance(plugin_id)


@app.websocket("/ws/streams/{plugin_id}")
async def websocket_stream(websocket: WebSocket, plugin_id: str) -> None:
    await websocket.accept()
    try:
        plugin = await get_plugin_instance(plugin_id, request_like=websocket)
    except HTTPException as exc:
        await websocket.send_json({"error": exc.detail})
        await websocket.close(code=4004)
        return

    LOGGER.info("WebSocket client subscribed to %s", plugin_id)
    try:
        async for chunk in transcode_to_opus(plugin):
            await websocket.send_bytes(chunk)
    except WebSocketDisconnect:
        LOGGER.info("WebSocket disconnected for %s", plugin_id)
    except Exception:  # pragma: no cover
        LOGGER.exception("Stream error for %s", plugin_id)
    finally:
        await manager.registry.release_instance(plugin_id)


@app.post("/streams/{plugin_id}/record")
async def record_stream(plugin_id: str, request: StreamRequest) -> dict[str, str]:
    duration = request.duration or 30
    try:
        plugin = await manager.registry.get_instance(plugin_id, **request.config)
    except (KeyError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    filename = f"{plugin_id}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.ogg"
    destination = Path(config.settings.recording_dir) / filename
    await record_opus(plugin, destination, duration_seconds=duration)
    await manager.registry.release_instance(plugin_id)

    return {
        "plugin_id": plugin_id,
        "recording_path": str(destination),
        "duration_seconds": duration,
    }
