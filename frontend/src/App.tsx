import { FormEvent, useEffect, useMemo, useState } from "react";
import StreamPlayer from "./components/StreamPlayer";

type PluginInfo = {
  plugin_id: string;
  display_name: string;
  legal_notice: string;
  capabilities: string[];
  disabled: boolean;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export default function App() {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [selectedPlugin, setSelectedPlugin] = useState<string>("");
  const [configText, setConfigText] = useState("{}");
  const [connectionConfig, setConnectionConfig] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/plugins`)
      .then((response) => response.json())
      .then((data: PluginInfo[]) => {
        setPlugins(data);
        if (data.length > 0) {
          setSelectedPlugin(data[0].plugin_id);
        }
      })
      .catch((err) => setError((err as Error).message));
  }, []);

  const currentPlugin = useMemo(
    () => plugins.find((plugin) => plugin.plugin_id === selectedPlugin) ?? null,
    [plugins, selectedPlugin]
  );

  function handleConnect(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const parsed = configText.trim() ? JSON.parse(configText) : {};
      setConnectionConfig(parsed);
    } catch (err) {
      setError(`Invalid config JSON: ${(err as Error).message}`);
    }
  }

  return (
    <div className="mx-auto max-w-4xl p-6">
      <header className="border-b border-slate-700 pb-4">
        <h1 className="text-3xl font-bold text-brand-light">ScannerForge</h1>
        <p className="text-sm text-slate-300">
          Legal radio stream orchestrator. Connect to public Broadcastify feeds, your own
          recordings, or SDR hardware on permitted bands.
        </p>
        <p className="mt-2 text-xs text-yellow-300">
          Never monitor encrypted, trunked, or access-controlled systems. Stick to ham, NOAA, and
          other lawful frequencies.
        </p>
      </header>

      <main className="mt-6 grid gap-6 md:grid-cols-2">
        <section className="space-y-4">
          <form onSubmit={handleConnect} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-semibold">Stream source</label>
              <select
                value={selectedPlugin}
                onChange={(event) => setSelectedPlugin(event.target.value)}
                className="w-full rounded border border-slate-600 bg-slate-800 p-2 text-slate-100"
              >
                {plugins.map((plugin) => (
                  <option key={plugin.plugin_id} value={plugin.plugin_id} disabled={plugin.disabled}>
                    {plugin.display_name}
                    {plugin.disabled ? " (disabled)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-semibold">Plugin config (JSON)</label>
              <textarea
                value={configText}
                onChange={(event) => setConfigText(event.target.value)}
                rows={6}
                className="w-full rounded border border-slate-600 bg-slate-800 p-2 font-mono text-xs text-slate-100"
                placeholder='{"stream_url": "https://example"}'
              />
            </div>
            {currentPlugin && (
              <div className="rounded border border-slate-700 bg-slate-800 p-3 text-xs text-slate-200">
                <p className="font-semibold">Legal Notice</p>
                <p>{currentPlugin.legal_notice}</p>
                <p className="mt-2 text-slate-400">Capabilities: {currentPlugin.capabilities.join(", ")}</p>
              </div>
            )}
            <button
              type="submit"
              className="w-full rounded bg-brand px-4 py-2 font-semibold text-white shadow hover:bg-brand-light"
              disabled={!selectedPlugin}
            >
              Connect
            </button>
            {error && <p className="text-sm text-red-400">{error}</p>}
          </form>
        </section>

        <section className="rounded border border-slate-700 bg-slate-800 p-4">
          {currentPlugin && connectionConfig ? (
            <StreamPlayer
              key={`${currentPlugin.plugin_id}-${JSON.stringify(connectionConfig)}`}
              pluginId={currentPlugin.plugin_id}
              config={connectionConfig}
              onDisconnect={() => setConnectionConfig(null)}
            />
          ) : (
            <p className="text-sm text-slate-300">
              Configure a plugin and press connect to start streaming Opus audio.
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
