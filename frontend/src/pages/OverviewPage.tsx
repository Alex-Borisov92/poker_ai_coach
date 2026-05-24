import { useEffect, useMemo, useState } from "react";

import {
  analyzeOverview,
  fetchDatabaseStatus,
  fetchHealthStatus,
  fetchOverviewReport,
} from "../api/client";
import type { CoachResponse, DatabaseStatus, HealthStatus, OverviewReport } from "../api/client";
import { CoachPanel } from "../components/CoachPanel";
import { StatCard } from "../components/StatCard";

type LoadState = "loading" | "ready" | "error";

export function OverviewPage() {
  const [databaseStatus, setDatabaseStatus] = useState<DatabaseStatus | null>(null);
  const [overviewReport, setOverviewReport] = useState<OverviewReport | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [coachResult, setCoachResult] = useState<CoachResponse | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [coachLoading, setCoachLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [coachError, setCoachError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadStatus() {
      try {
        const [databaseData, overviewData, healthData] = await Promise.all([
          fetchDatabaseStatus(),
          fetchOverviewReport(),
          fetchHealthStatus(),
        ]);
        if (!isActive) {
          return;
        }
        setDatabaseStatus(databaseData);
        setOverviewReport(overviewData);
        setHealthStatus(healthData);
        setLoadState("ready");
      } catch (loadError) {
        if (!isActive) {
          return;
        }
        setLoadState("error");
        setError(loadError instanceof Error ? loadError.message : "Backend unavailable");
      }
    }

    loadStatus();

    return () => {
      isActive = false;
    };
  }, []);

  const statusTone = useMemo(() => {
    if (loadState === "error") {
      return "bad";
    }
    if (!databaseStatus?.configured) {
      return "warning";
    }
    return databaseStatus.connected ? "good" : "bad";
  }, [databaseStatus, loadState]);

  const statusLabel = useMemo(() => {
    if (loadState === "loading") {
      return "Loading";
    }
    if (loadState === "error") {
      return "Backend error";
    }
    if (!databaseStatus?.configured) {
      return "Not configured";
    }
    return databaseStatus.connected ? "Connected" : "Disconnected";
  }, [databaseStatus, loadState]);

  const tableRows = Object.entries(databaseStatus?.table_counts ?? {});
  const overviewWarnings = overviewReport?.warnings ?? databaseStatus?.warnings ?? [];
  const hasOverviewRows = Boolean(
    overviewReport &&
      (overviewReport.total_hands ||
        overviewReport.tournaments ||
        overviewReport.imported_files ||
        overviewReport.error_hands),
  );
  const dateRange =
    overviewReport?.valid_date_range.start && overviewReport.valid_date_range.end
      ? `${overviewReport.valid_date_range.start} to ${overviewReport.valid_date_range.end}`
      : "Unknown";
  const canRunCoach = Boolean(healthStatus?.ai_enabled && healthStatus.ai_configured);
  const coachDisabledReason = !healthStatus?.ai_enabled
    ? "AI is disabled. Set AI_ENABLED=true and configure OPENAI_API_KEY to enable review."
    : !healthStatus.ai_configured
      ? "OPENAI_API_KEY is missing. No report data will be sent."
      : "Coach unavailable.";

  async function reviewSession() {
    setCoachLoading(true);
    setCoachError(null);
    setCoachResult(null);
    try {
      const result = await analyzeOverview();
      setCoachResult(result);
    } catch (loadError) {
      setCoachError(loadError instanceof Error ? loadError.message : "Coach request failed");
    } finally {
      setCoachLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Overview</h1>
          <p>Historical HM3 summary for post-session review.</p>
        </div>
        <div className={`status-pill ${statusTone}`}>{statusLabel}</div>
      </header>

      <div className="overview-layout">
        <div className="overview-main">
          {loadState === "loading" ? (
            <section className="panel loading-panel">
              <h2>Loading overview</h2>
              <p>Reading local database status in read-only mode.</p>
            </section>
          ) : null}

          <section className="stats-grid" aria-label="Status summary">
            <StatCard label="Hands" value={overviewReport?.total_hands ?? 0} tone={statusTone} />
            <StatCard label="Tournaments" value={overviewReport?.tournaments ?? 0} />
            <StatCard label="Imported files" value={overviewReport?.imported_files ?? 0} />
            <StatCard
              label="Error hands"
              value={overviewReport?.error_hands ?? 0}
              tone={overviewReport?.error_hands ? "warning" : "neutral"}
            />
            <StatCard label="Valid date range" value={dateRange} />
            <StatCard
              label="Invalid dates"
              value={overviewReport?.invalid_1970_date_count ?? 0}
              tone={overviewReport?.invalid_1970_date_count ? "warning" : "neutral"}
            />
          </section>

          {loadState === "error" ? (
            <section className="panel error-panel">
              <h2>Backend unavailable</h2>
              <p>{error}</p>
              <ul className="recovery-list">
                <li>Start the backend with uvicorn.</li>
                <li>Check VITE_API_BASE_URL if you use a custom API port.</li>
                <li>Open Database status after backend restarts.</li>
              </ul>
            </section>
          ) : null}

          {databaseStatus?.error ? (
            <section className="panel error-panel">
              <h2>Database error</h2>
              <p>{databaseStatus.error}</p>
            </section>
          ) : null}

          {overviewReport?.error ? (
            <section className="panel error-panel">
              <h2>Overview error</h2>
              <p>{overviewReport.error}</p>
            </section>
          ) : null}

          {loadState === "ready" && overviewReport?.connected && !hasOverviewRows ? (
            <section className="panel empty-panel">
              <h2>No overview data</h2>
              <p>No hands, tournaments, imported files, or error hands were found.</p>
            </section>
          ) : null}

          {overviewWarnings.length ? (
            <section className="panel warning-panel">
              <h2>Warnings</h2>
              <ul>
                {overviewWarnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="panel">
            <div className="panel-header">
              <h2>Overview details</h2>
              <span>{overviewReport?.hero_found ? "Hero found" : "Hero not found"}</span>
            </div>
            <div className="detail-grid">
              <div>
                <span>Hero</span>
                <strong>{overviewReport?.hero_name ?? healthStatus?.hero_name ?? "Unknown"}</strong>
              </div>
              <div>
                <span>Valid hand dates</span>
                <strong>{overviewReport?.valid_date_count ?? 0}</strong>
              </div>
              <div>
                <span>Missing HM3 tables</span>
                <strong>{overviewReport?.missing_tables.length ?? 0}</strong>
              </div>
              <div>
                <span>Status</span>
                <strong>{statusLabel}</strong>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>HM3 table counts</h2>
              <span>{tableRows.length} checked</span>
            </div>
            {tableRows.length ? (
              <table>
                <thead>
                  <tr>
                    <th>Table</th>
                    <th>Rows</th>
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map(([tableName, rowCount]) => (
                    <tr key={tableName}>
                      <td>{tableName}</td>
                      <td>{rowCount}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="empty-state">No table counts yet.</p>
            )}
          </section>
        </div>

        <aside className="coach-preview" aria-label="AI coach preview">
          <CoachPanel
            actionLabel="Review session"
            canRun={canRunCoach}
            disabledReason={coachDisabledReason}
            error={coachError}
            isLoading={coachLoading}
            onRun={reviewSession}
            result={coachResult}
          />

          <div className="panel">
            <div className="panel-header">
              <h2>Current scope</h2>
            </div>
            <p className="scope-text">
              This action sends only the Overview report JSON. Other pages have their own
              coach actions.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
