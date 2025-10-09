"""Integration tests covering FastAPI routes."""
from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.plugins.base import StreamPlugin


class StubPlugin(StreamPlugin):
    plugin_id = "stub"
    display_name = "Stub"
    legal_notice = ""
    capabilities = ["test"]

    def __init__(self, **config):
        super().__init__(**config)
        self._meta = config or {"note": "ok"}

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    def metadata(self) -> dict:
        return self._meta

    async def stream_chunks(self) -> AsyncGenerator[bytes, None]:
        yield b"pcm-data"


async def fake_transcode(plugin: StreamPlugin) -> AsyncGenerator[bytes, None]:
    yield b"opus-data"


@pytest.fixture(autouse=True)
def _patch_registry(monkeypatch):
    from app import main, plugins

    async def fake_get_instance(plugin_id: str, **config):
        return StubPlugin(**config)

    async def fake_release(plugin_id: str):
        return None

    monkeypatch.setattr(plugins.manager.registry, "get_instance", fake_get_instance)
    monkeypatch.setattr(plugins.manager.registry, "release_instance", fake_release)
    monkeypatch.setattr(main, "transcode_to_opus", fake_transcode)

    async def fake_record(plugin: StreamPlugin, destination, duration_seconds=30):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"opus-recording")
        return destination

    monkeypatch.setattr(main, "record_opus", fake_record)


def test_plugin_metadata_round_trip():
    client = TestClient(app)
    response = client.get("/streams/stub/metadata", params={"note": "demo"})
    assert response.status_code == 200
    assert response.json()["note"] == "demo"


def test_websocket_stream_flow():
    client = TestClient(app)
    with client.websocket_connect("/ws/streams/stub?quality=high") as websocket:
        data = websocket.receive_bytes()
        assert data == b"opus-data"


def test_record_endpoint(tmp_path):
    client = TestClient(app)
    from app import config

    config.settings.recording_dir = str(tmp_path)
    payload = {"config": {"note": "record"}, "duration": 5}
    response = client.post("/streams/stub/record", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["duration_seconds"] == 5
