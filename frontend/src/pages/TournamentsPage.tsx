import { useEffect, useState, type FormEvent } from "react";

import {
  fetchHealthStatus,
  fetchTournamentHands,
  fetchTournaments,
  type HandSummary,
  type HealthStatus,
  type TournamentFilters,
  type TournamentHands,
  type TournamentList,
  type TournamentSummary,
} from "../api/client";
import { CoachPanel } from "../components/CoachPanel";

type LoadState = "loading" | "ready" | "error";

const defaultFilters: TournamentFilters = {
  dateFrom: "",
  dateTo: "",
  search: "",
  onlyWithErrors: false,
  limit: 100,
};

export function TournamentsPage() {
  const [filters, setFilters] = useState<TournamentFilters>(defaultFilters);
  const [draftFilters, setDraftFilters] = useState<TournamentFilters>(defaultFilters);
  const [report, setReport] = useState<TournamentList | null>(null);
  const [selectedTournament, setSelectedTournament] = useState<string | null>(null);
  const [relatedHands, setRelatedHands] = useState<TournamentHands | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [handsLoadState, setHandsLoadState] = useState<LoadState>("ready");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadTournaments() {
      setLoadState("loading");
      setError(null);
      try {
        const [tournamentData, healthData] = await Promise.all([
          fetchTournaments(filters),
          fetchHealthStatus(),
        ]);
        if (!isActive) {
          return;
        }
        setReport(tournamentData);
        setHealthStatus(healthData);
        setLoadState("ready");

        const firstTournament = tournamentData.tournaments[0];
        if (firstTournament) {
          await selectTournament(firstTournament, isActive);
        } else {
          setSelectedTournament(null);
          setRelatedHands(null);
        }
      } catch (loadError) {
        if (!isActive) {
          return;
        }
        setLoadState("error");
        setError(loadError instanceof Error ? loadError.message : "Backend unavailable");
      }
    }

    loadTournaments();

    return () => {
      isActive = false;
    };
  }, [filters]);

  async function selectTournament(tournament: TournamentSummary, isStillActive = true) {
    setSelectedTournament(tournament.tournament_number);
    setRelatedHands(null);
    setHandsLoadState("loading");
    try {
      const handsData = await fetchTournamentHands(tournament.tournament_number, 100);
      if (!isStillActive) {
        return;
      }
      setRelatedHands(handsData);
      setHandsLoadState("ready");
    } catch (loadError) {
      if (!isStillActive) {
        return;
      }
      setHandsLoadState("error");
      setRelatedHands({
        configured: true,
        connected: false,
        tournament_number: tournament.tournament_number,
        database_name: report?.database_name ?? null,
        hands: [],
        warnings: [],
        error: loadError instanceof Error ? loadError.message : "Tournament hands unavailable",
      });
    }
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilters({ ...draftFilters });
  }

  function resetFilters() {
    setDraftFilters(defaultFilters);
    setFilters(defaultFilters);
  }

  const warnings = [...(report?.warnings ?? []), ...(relatedHands?.warnings ?? [])];
  const coachDisabledReason = healthStatus?.ai_enabled
    ? "Tournament coach review is not implemented yet. Use Overview, Leak Finder, or Hand Review."
    : "AI is disabled. Tournament browsing stays local and read-only.";

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Tournaments</h1>
          <p>Browse historical HM3 tournaments and open related hands.</p>
        </div>
        <div className={report?.connected ? "status-pill good" : "status-pill warning"}>
          {report?.connected ? "Connected" : "Disconnected"}
        </div>
      </header>

      <div className="hand-review-layout">
        <div className="hand-review-main">
          <section className="panel">
            <div className="panel-header">
              <h2>Filters</h2>
              <span>{report?.database_name ?? "No database"}</span>
            </div>
            <form className="filter-bar" onSubmit={applyFilters}>
              <label>
                <span>From</span>
                <input
                  onChange={(event) =>
                    setDraftFilters({ ...draftFilters, dateFrom: event.target.value })
                  }
                  type="date"
                  value={draftFilters.dateFrom ?? ""}
                />
              </label>
              <label>
                <span>To</span>
                <input
                  onChange={(event) =>
                    setDraftFilters({ ...draftFilters, dateTo: event.target.value })
                  }
                  type="date"
                  value={draftFilters.dateTo ?? ""}
                />
              </label>
              <label className="filter-search">
                <span>Search</span>
                <input
                  onChange={(event) =>
                    setDraftFilters({ ...draftFilters, search: event.target.value })
                  }
                  placeholder="Tournament number"
                  type="search"
                  value={draftFilters.search ?? ""}
                />
              </label>
              <label className="checkbox-field">
                <input
                  checked={Boolean(draftFilters.onlyWithErrors)}
                  onChange={(event) =>
                    setDraftFilters({
                      ...draftFilters,
                      onlyWithErrors: event.target.checked,
                    })
                  }
                  type="checkbox"
                />
                <span>Only with errors</span>
              </label>
              <div className="filter-actions">
                <button className="primary-action" type="submit">
                  Apply
                </button>
                <button className="primary-action" onClick={resetFilters} type="button">
                  Reset
                </button>
              </div>
            </form>
          </section>

          {loadState === "loading" ? (
            <section className="panel loading-panel">
              <h2>Loading tournaments</h2>
              <p>Reading historical tournaments in read-only mode.</p>
            </section>
          ) : null}

          {loadState === "error" ? (
            <section className="panel error-panel">
              <h2>Backend unavailable</h2>
              <p>{error}</p>
              <ul className="recovery-list">
                <li>Start the backend with uvicorn.</li>
                <li>Check that HM3_DB_PATH points to a local .hmdb file.</li>
                <li>Reload this page after backend restarts.</li>
              </ul>
            </section>
          ) : null}

          {report?.error ? (
            <section className="panel error-panel">
              <h2>Tournament report error</h2>
              <p>{report.error}</p>
            </section>
          ) : null}

          {warnings.length ? (
            <section className="panel warning-panel">
              <h2>Warnings</h2>
              <ul>
                {warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="panel">
            <div className="panel-header">
              <h2>Tournament list</h2>
              <span>{report?.tournaments.length ?? 0} tournaments</span>
            </div>
            {report?.tournaments.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Tournament</th>
                      <th>Date range</th>
                      <th>Buy-in</th>
                      <th>Entrants</th>
                      <th>Hands</th>
                      <th>Errors</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.tournaments.map((tournament) => (
                      <tr
                        className={
                          tournament.tournament_number === selectedTournament ? "selected-row" : ""
                        }
                        key={tournament.tournament_number}
                        onClick={() => selectTournament(tournament)}
                      >
                        <td>{tournament.tournament_number}</td>
                        <td>{formatDateRange(tournament)}</td>
                        <td>{formatBuyIn(tournament)}</td>
                        <td>{tournament.entrants ?? "Unknown"}</td>
                        <td>{tournament.hand_count}</td>
                        <td>{tournament.error_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : loadState === "ready" ? (
              <p className="empty-state">No tournaments matched the current filters.</p>
            ) : null}
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>Related hands</h2>
              <span>{selectedTournament ?? "Select tournament"}</span>
            </div>
            {handsLoadState === "loading" ? (
              <p className="empty-state">Loading hands for selected tournament.</p>
            ) : null}
            {relatedHands?.error ? (
              <p className="empty-state">{relatedHands.error}</p>
            ) : null}
            {relatedHands?.hands.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Hand ID</th>
                      <th>Date</th>
                      <th>Reason</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {relatedHands.hands.map((hand: HandSummary) => (
                      <tr key={hand.hand_id}>
                        <td>{hand.hand_id}</td>
                        <td>{hand.hand_date ?? "Unknown"}</td>
                        <td>{hand.reasons.join(", ")}</td>
                        <td>{hand.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : handsLoadState === "ready" && selectedTournament ? (
              <p className="empty-state">No hand text was found for this tournament.</p>
            ) : null}
          </section>
        </div>

        <aside className="coach-preview" aria-label="AI coach preview">
          <CoachPanel
            actionLabel="Ask coach"
            canRun={false}
            disabledReason={coachDisabledReason}
            error={null}
            isLoading={false}
            onRun={() => undefined}
            result={null}
          />
        </aside>
      </div>
    </div>
  );
}

function formatDateRange(tournament: TournamentSummary): string {
  if (!tournament.first_hand_date || !tournament.last_hand_date) {
    return "Unknown";
  }
  if (tournament.first_hand_date === tournament.last_hand_date) {
    return tournament.first_hand_date;
  }
  return `${tournament.first_hand_date} to ${tournament.last_hand_date}`;
}

function formatBuyIn(tournament: TournamentSummary): string {
  const buyin = formatCents(tournament.buyin_in_cents);
  const rake = formatCents(tournament.rake_in_cents);
  const bounty = formatCents(tournament.bounty_in_cents);
  if (buyin === "Unknown" && rake === "Unknown" && bounty === "Unknown") {
    return "Unknown";
  }
  return `${buyin} + ${rake}${tournament.bounty_in_cents ? ` bounty ${bounty}` : ""}`;
}

function formatCents(value: number | null): string {
  if (value === null) {
    return "Unknown";
  }
  return `$${(value / 100).toFixed(2)}`;
}
