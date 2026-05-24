import { useEffect, useState, type FormEvent } from "react";

import {
  createExplorerSnapshot,
  fetchDatabaseStatus,
  fetchHealthStatus,
  setDatabasePath,
  type DatabaseStatus,
  type ExplorerSnapshotResponse,
  type HealthStatus,
} from "../api/client";

type LoadState = "loading" | "ready" | "error";

export function SettingsPage() {
  const [databaseStatus, setDatabaseStatus] = useState<DatabaseStatus | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [databasePath, setDatabasePathInput] = useState("");
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [isSaving, setIsSaving] = useState(false);
  const [isCreatingSnapshot, setIsCreatingSnapshot] = useState(false);
  const [snapshotResult, setSnapshotResult] = useState<ExplorerSnapshotResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStatus();
  }, []);

  async function loadStatus() {
    setLoadState("loading");
    setError(null);
    try {
      const [databaseData, healthData] = await Promise.all([
        fetchDatabaseStatus(),
        fetchHealthStatus(),
      ]);
      setDatabaseStatus(databaseData);
      setHealthStatus(healthData);
      setLoadState("ready");
    } catch (loadError) {
      setLoadState("error");
      setError(loadError instanceof Error ? loadError.message : "Backend unavailable");
    }
  }

  async function submitDatabasePath(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedPath = databasePath.trim();
    if (!trimmedPath) {
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      const status = await setDatabasePath(trimmedPath);
      setDatabaseStatus(status);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Database path check failed");
    } finally {
      setIsSaving(false);
    }
  }

  async function createSnapshot() {
    setIsCreatingSnapshot(true);
    setError(null);
    setSnapshotResult(null);
    try {
      const result = await createExplorerSnapshot();
      setSnapshotResult(result);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Snapshot creation failed");
    } finally {
      setIsCreatingSnapshot(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Load a local HM3 database and check safe app configuration.</p>
        </div>
        <div className={databaseStatus?.connected ? "status-pill good" : "status-pill warning"}>
          {databaseStatus?.connected ? "DB connected" : "DB missing"}
        </div>
      </header>

      <div className="overview-layout">
        <div className="overview-main">
          {loadState === "error" ? (
            <section className="panel error-panel">
              <h2>Backend unavailable</h2>
              <p>{error}</p>
              <ul className="recovery-list">
                <li>Start the backend with uvicorn.</li>
                <li>Reload Settings after backend restarts.</li>
              </ul>
            </section>
          ) : null}

          <section className="panel">
            <div className="panel-header">
              <h2>Load HM3 database</h2>
              <span>Read-only check</span>
            </div>
            <form className="settings-form" onSubmit={submitDatabasePath}>
              <label>
                <span>HM3 DB path</span>
                <input
                  onChange={(event) => setDatabasePathInput(event.target.value)}
                  placeholder="C:\\path\\to\\database.hmdb"
                  type="text"
                  value={databasePath}
                />
              </label>
              <button className="primary-action" disabled={isSaving || !databasePath.trim()} type="submit">
                {isSaving ? "Checking..." : "Load database"}
              </button>
            </form>
            <p className="scope-text">
              Paste the full local path. The app does not upload or copy the HM3 file.
              This button uses the path for the current backend session only.
            </p>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>Database status</h2>
              <span>{loadState === "loading" ? "Loading" : "Current"}</span>
            </div>
            <div className="detail-grid">
              <div>
                <span>Configured</span>
                <strong>{databaseStatus?.configured ? "Yes" : "No"}</strong>
              </div>
              <div>
                <span>Connected</span>
                <strong>{databaseStatus?.connected ? "Yes" : "No"}</strong>
              </div>
              <div>
                <span>Database</span>
                <strong>{databaseStatus?.database_name ?? "None"}</strong>
              </div>
              <div>
                <span>Tables</span>
                <strong>{databaseStatus?.tables.length ?? 0}</strong>
              </div>
            </div>

            {databaseStatus?.error ? (
              <div className="coach-result error-panel">
                <strong>Error</strong>
                <p>{databaseStatus.error}</p>
              </div>
            ) : null}

            {databaseStatus?.warnings.length ? (
              <div className="coach-result warning-panel">
                <strong>Warnings</strong>
                <ul>
                  {databaseStatus.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>.env file</h2>
              <span>Persistent config</span>
            </div>
            <p className="scope-text">
              Put `.env` in the project root next to README.md.
            </p>
            <pre className="config-snippet">{envExample}</pre>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>DBeaver explorer snapshot</h2>
              <span>Sanitized SQLite</span>
            </div>
            <p className="scope-text">
              Creates a local schema-only SQLite snapshot in local_exports. It does not include
              hand text, API keys, full source paths, or the original HM3 database.
            </p>
            <button
              className="primary-action"
              disabled={!databaseStatus?.connected || isCreatingSnapshot}
              onClick={createSnapshot}
              type="button"
            >
              {isCreatingSnapshot ? "Creating..." : "Create snapshot"}
            </button>
            {snapshotResult ? (
              <div className={snapshotResult.created ? "coach-result" : "coach-result error-panel"}>
                <strong>{snapshotResult.created ? "Snapshot ready" : "Snapshot failed"}</strong>
                <p>{snapshotResult.relative_path ?? snapshotResult.error}</p>
                {snapshotResult.warnings.length ? (
                  <ul>
                    {snapshotResult.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </section>
        </div>

        <aside className="coach-preview" aria-label="Settings summary">
          <section className="panel coach-panel">
            <div className="panel-header">
              <h2>Runtime</h2>
              <span>{healthStatus?.status ?? "Unknown"}</span>
            </div>
            <div className="coach-preview-list">
              <span>Hero</span>
              <p>{healthStatus?.hero_name ?? "surok_valera"}</p>
              <span>AI</span>
              <p>
                {healthStatus?.ai_enabled
                  ? healthStatus.ai_configured
                    ? "Enabled"
                    : "API key missing"
                  : "Disabled"}
              </p>
              <span>Safety</span>
              <p>HM3 DB is opened read-only. No live table or poker client integration.</p>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

const envExample = `HM3_DB_PATH=C:\\path\\to\\database.hmdb
HERO_NAME=surok_valera
AI_ENABLED=false
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
APP_HOST=127.0.0.1
APP_PORT=8000`;
