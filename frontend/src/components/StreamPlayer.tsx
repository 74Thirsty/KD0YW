import { useEffect, useMemo, useRef, useState } from "react";

type Props = {
  pluginId: string;
  config: Record<string, unknown>;
  onDisconnect: () => void;
};

type ConnectionState = "idle" | "connecting" | "streaming" | "error";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

function buildQuery(config: Record<string, unknown>): string {
  const params = new URLSearchParams();
  Object.entries(config).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    params.append(key, String(value));
  });
  return params.toString();
}

export function StreamPlayer({ pluginId, config, onDisconnect }: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const sourceBufferRef = useRef<SourceBuffer | null>(null);
  const queueRef = useRef<Uint8Array[]>([]);
  const websocketRef = useRef<WebSocket | null>(null);
  const [state, setState] = useState<ConnectionState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [recordingPath, setRecordingPath] = useState<string | null>(null);

  const wsUrl = useMemo(() => {
    const base = new URL(API_BASE);
    base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
    base.pathname = `/ws/streams/${pluginId}`;
    const query = buildQuery(config);
    base.search = query;
    return base.toString();
  }, [pluginId, config]);

  useEffect(() => {
    const audioEl = audioRef.current;
    if (!audioEl) return;

    const mediaSource = new MediaSource();
    const objectUrl = URL.createObjectURL(mediaSource);
    audioEl.src = objectUrl;

    const flushQueue = () => {
      const buffer = sourceBufferRef.current;
      if (!buffer || buffer.updating) return;
      const next = queueRef.current.shift();
      if (next) {
        buffer.appendBuffer(next);
      }
    };

    const handleSourceOpen = () => {
      const sourceBuffer = mediaSource.addSourceBuffer("audio/ogg; codecs=opus");
      sourceBuffer.mode = "sequence";
      sourceBufferRef.current = sourceBuffer;
      sourceBuffer.addEventListener("updateend", flushQueue);
    };

    mediaSource.addEventListener("sourceopen", handleSourceOpen);

    return () => {
      mediaSource.removeEventListener("sourceopen", handleSourceOpen);
      const buffer = sourceBufferRef.current;
      if (buffer) {
        buffer.removeEventListener("updateend", flushQueue);
      }
      URL.revokeObjectURL(objectUrl);
      sourceBufferRef.current = null;
      queueRef.current = [];
    };
  }, [wsUrl]);

  useEffect(() => {
    setState("connecting");
    setError(null);
    setRecordingPath(null);

    const ws = new WebSocket(wsUrl);
    websocketRef.current = ws;

    ws.binaryType = "arraybuffer";
    ws.onopen = () => {
      setState("streaming");
    };
    ws.onerror = () => {
      setError("WebSocket error");
      setState("error");
    };
    ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        const payload = JSON.parse(event.data);
        if (payload.error) {
          setError(payload.error);
          setState("error");
        }
        return;
      }
      const chunk = new Uint8Array(event.data);
      const buffer = sourceBufferRef.current;
      if (buffer && !buffer.updating) {
        try {
          buffer.appendBuffer(chunk);
        } catch (err) {
          console.error("append error", err);
        }
      } else {
        queueRef.current.push(chunk);
      }
    };
    ws.onclose = () => {
      setState((prev) => (prev === "error" ? prev : "idle"));
      onDisconnect();
    };

    return () => {
      ws.close(1000, "client disconnect");
      websocketRef.current = null;
    };
  }, [wsUrl, onDisconnect]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      const buffer = sourceBufferRef.current;
      if (!buffer || buffer.updating) return;
      const next = queueRef.current.shift();
      if (next) {
        buffer.appendBuffer(next);
      }
    }, 200);
    return () => window.clearInterval(interval);
  }, []);

  async function handleRecord() {
    try {
      const response = await fetch(`${API_BASE}/streams/${pluginId}/record`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config, duration: 30 })
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const data = await response.json();
      setRecordingPath(data.recording_path);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="mt-4 space-y-4">
      <div className="flex items-center gap-3 text-sm">
        <span className="font-mono uppercase tracking-wide">
          State: {state}
        </span>
        {error && <span className="text-red-400">{error}</span>}
        {recordingPath && (
          <span className="text-brand-light">Saved to {recordingPath}</span>
        )}
      </div>
      <audio ref={audioRef} controls className="w-full" />
      <div className="flex gap-3">
        <button
          onClick={handleRecord}
          className="rounded bg-brand px-4 py-2 text-white shadow hover:bg-brand-light"
        >
          Record 30s Clip
        </button>
        <button
          onClick={() => websocketRef.current?.close(1000)}
          className="rounded border border-slate-500 px-4 py-2 text-slate-100 hover:bg-slate-800"
        >
          Disconnect
        </button>
      </div>
    </div>
  );
}

export default StreamPlayer;
