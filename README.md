# KD0YW

KD0YW is a legal-first radio streaming stack. It ingests public HTTP feeds, authorized
local files, and RTL-SDR captures in permissible bands, then transcodes and serves Opus audio to a
React dashboard. The stack is modular so new lawful plugins can be dropped in without touching the
core.

## ⚖️ Legal guardrails

- **Never** attempt to monitor encrypted, trunked, or access-controlled systems. This project will
  refuse such requests.
- Stick to public Broadcastify feeds, NOAA weather, ham repeaters, and other unencrypted services.
- When adding plugins, document the legal basis in `legal_notice` and surface it to operators.

## Architecture

```
┌────────────┐   websockets   ┌──────────────┐
│ FastAPI    │◀──────────────▶│ React/Vite UI│
│  plugins   │    REST API    │  WebAudio    │
└────┬───────┘                └────┬─────────┘
     │ Redis pub/sub               │
     │                              │
┌────▼─────┐  ffmpeg  ┌─────────────▼─────┐
│Plugins   │────────▶│ Opus/Ogg pipeline │
│(HTTP,    │         │ recording engine  │
│ File,    │         │ 30s clip capture  │
│ RTL-SDR) │         └───────────────────┘
└──────────┘
```

### Key components

- **Backend** – FastAPI 0.110+, SQLAlchemy stub, Redis pub/sub hooks, and a plugin registry.
- **Audio pipeline** – `ffmpeg` is spawned to transcode arbitrary inputs into `audio/ogg; codecs=opus`
  for browser playback. The same pipeline records 30 second clips on demand.
- **Frontend** – React + Vite + Tailwind UI that selects plugins, shows legal notices, and plays
  WebSocket audio through the MediaSource API.
- **DevOps** – Docker Compose spins up PostgreSQL, Redis, backend, and frontend containers. CI hooks
  can call `pytest` and frontend build commands.

## Getting started

### Prerequisites

- Docker + Docker Compose
- (Optional) Python 3.11 & Node 20 if you prefer running without containers
- `ffmpeg` available on your PATH for direct execution

### Clone and boot

```bash
git clone <repo>
cd KD0YW
docker compose up --build
```

Backend is available on <http://localhost:8000>, frontend on <http://localhost:5173>.

### Local development without Docker

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## End-to-end walkthrough

1. Launch the stack (`docker compose up --build`).
2. Visit the frontend, choose the **Broadcastify Public Feed** plugin, and paste a public feed URL
   into the JSON config, e.g. `{ "stream_url": "https://.../listen.pls" }`.
3. Hit **Connect** – the backend fetches the HTTP stream, `ffmpeg` transcodes it to Ogg/Opus, and the
   browser plays it over WebAudio.
4. Click **Record 30s Clip** to capture a short sample. Clips are saved under
   `backend/data/recordings` (or `/data/recordings` in Docker) and surfaced in the UI.

The **Local File** plugin can be used for offline testing – point it at a WAV/MP3 you own. The
**RTL-SDR (Legal Bands Only)** adapter requires explicit `center_frequency` (>=100 MHz), `sample_rate`,
and optional gain. It only supports unencrypted amateur/weather bands and will refuse unsafe values.

## Plugin contract & authoring guide

All plugins inherit from `StreamPlugin` (`app/plugins/base.py`):

```python
class StreamPlugin(abc.ABC):
    plugin_id: str
    display_name: str
    legal_notice: str
    capabilities: list[str]

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def metadata(self) -> dict: ...
    async def stream_chunks(self) -> AsyncGenerator[bytes, None]: ...
```

Implementations should:

- Validate configuration in `__init__` / `start` and raise helpful errors.
- Stream raw audio bytes; the registry automatically pipes them through the Opus encoder.
- Populate `legal_notice` and `capabilities` so the UI can describe the stream.
- Avoid retaining resources after `stop()` – the registry controls lifecycle.

To add a plugin:

1. Create `app/plugins/<name>.py` exporting your class.
2. Register it inside `app/main.startup()` or through a discovery hook.
3. Document the legal context in README updates.
4. Add tests covering metadata and streaming behaviour.

## Security & audit hooks

- Admin endpoints (`/admin/plugins/{id}/disable|enable`) let operators hard-stop a plugin without
  redeploys.
- Every plugin logs its URI/frequency and honours `SCANNERFORGE_RECORDING_DIR` so recordings stay in
  a managed tree.
- The recording endpoint requires explicit user action and logs the saved clip path.

## Testing

Run backend tests with `pytest`:

```bash
cd backend
pytest
```

This covers plugin registry behaviour and a patched integration flow (websocket + recording). Expand
with live tests as hardware becomes available.

Frontend lint/build:

```bash
cd frontend
npm run lint
npm run build
```

## Observability & next steps

- Wire Redis pub/sub to broadcast metadata/state changes to multiple listeners.
- Add PostgreSQL models for plugin configurations, audit logs, and recording indices.
- Extend CI (`.github/workflows/ci.yml`) to lint both frontend and backend and to run pytest inside
  Docker.
- Harden the MediaSource player with buffering analytics and fallback audio workers.
