import { useEffect, useState } from "react";

import {
  fetchHandDetail,
  fetchHandReviewQueue,
  fetchHealthStatus,
  reviewHand,
  type CoachResponse,
  type HandDetail,
  type HandReviewQueue,
  type HandSummary,
  type HealthStatus,
} from "../api/client";
import { CoachPanel } from "../components/CoachPanel";
import { HandTextViewer } from "../components/HandTextViewer";

type LoadState = "loading" | "ready" | "error";

export function HandReviewPage() {
  const [queue, setQueue] = useState<HandReviewQueue | null>(null);
  const [selectedHand, setSelectedHand] = useState<HandDetail | null>(null);
  const [selectedHandId, setSelectedHandId] = useState<number | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [coachResult, setCoachResult] = useState<CoachResponse | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [handLoadState, setHandLoadState] = useState<LoadState>("ready");
  const [coachLoading, setCoachLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [coachError, setCoachError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadQueue() {
      try {
        const [queueData, healthData] = await Promise.all([
          fetchHandReviewQueue(50),
          fetchHealthStatus(),
        ]);
        if (!isActive) {
          return;
        }
        setQueue(queueData);
        setHealthStatus(healthData);
        setLoadState("ready");

        const firstHand = queueData.hands[0];
        if (firstHand) {
          setSelectedHandId(firstHand.hand_id);
          await loadHand(firstHand.hand_id, isActive);
        }
      } catch (loadError) {
        if (!isActive) {
          return;
        }
        setLoadState("error");
        setError(loadError instanceof Error ? loadError.message : "Backend unavailable");
      }
    }

    async function loadHand(handId: number, isStillActive: boolean) {
      setHandLoadState("loading");
      const handData = await fetchHandDetail(handId);
      if (!isStillActive) {
        return;
      }
      setSelectedHand(handData);
      setHandLoadState("ready");
    }

    loadQueue();

    return () => {
      isActive = false;
    };
  }, []);

  async function selectHand(hand: HandSummary) {
    setSelectedHandId(hand.hand_id);
    setSelectedHand(null);
    setCoachResult(null);
    setCoachError(null);
    setHandLoadState("loading");
    try {
      const handData = await fetchHandDetail(hand.hand_id);
      setSelectedHand(handData);
      setHandLoadState("ready");
    } catch (loadError) {
      setHandLoadState("error");
      setSelectedHand({
        configured: true,
        connected: false,
        hand_id: hand.hand_id,
        tournament_number: hand.tournament_number,
        hand_date: hand.hand_date,
        is_date_unknown: hand.is_date_unknown,
        source: hand.source,
        hand_text: "",
        warnings: [],
        error: loadError instanceof Error ? loadError.message : "Hand unavailable",
      });
    }
  }

  const warnings = queue?.warnings ?? [];
  const canRunCoach = Boolean(
    healthStatus?.ai_enabled && healthStatus.ai_configured && selectedHandId,
  );
  const coachDisabledReason = !healthStatus?.ai_enabled
    ? "AI is disabled. Set AI_ENABLED=true and configure OPENAI_API_KEY to enable hand review."
    : !healthStatus.ai_configured
      ? "OPENAI_API_KEY is missing. No hand text will be sent."
      : !selectedHandId
        ? "Select a historical hand first."
        : "Coach unavailable.";

  async function reviewSelectedHand() {
    if (!selectedHandId) {
      return;
    }
    setCoachLoading(true);
    setCoachError(null);
    setCoachResult(null);
    try {
      const result = await reviewHand(selectedHandId);
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
          <h1>Hand Review</h1>
          <p>Historical hands selected for post-session review.</p>
        </div>
        <button
          className="primary-action"
          disabled={!canRunCoach || coachLoading}
          onClick={reviewSelectedHand}
          type="button"
        >
          Review this hand
        </button>
      </header>

      <div className="hand-review-layout">
        <div className="hand-review-main">
          {loadState === "loading" ? (
            <section className="panel loading-panel">
              <h2>Loading hand queue</h2>
              <p>Reading historical hands in read-only mode.</p>
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

          {queue?.error ? (
            <section className="panel error-panel">
              <h2>Hand queue error</h2>
              <p>{queue.error}</p>
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
              <h2>Review queue</h2>
              <span>{queue?.hands.length ?? 0} hands</span>
            </div>
            {queue?.hands.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Hand ID</th>
                      <th>Tournament</th>
                      <th>Date</th>
                      <th>Reason</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {queue.hands.map((hand) => (
                      <tr
                        className={hand.hand_id === selectedHandId ? "selected-row" : ""}
                        key={hand.hand_id}
                        onClick={() => selectHand(hand)}
                      >
                        <td>{hand.hand_id}</td>
                        <td>{hand.tournament_number ?? "Unknown"}</td>
                        <td>{hand.hand_date ?? "Unknown"}</td>
                        <td>{hand.reasons.join(", ")}</td>
                        <td>{hand.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : loadState === "ready" ? (
              <p className="empty-state">No hands matched the review queue rules.</p>
            ) : null}
          </section>

          <section className="panel hand-viewer-panel">
            <div className="panel-header">
              <h2>Hand text</h2>
              <span>{selectedHand?.hand_date ?? "Date unknown"}</span>
            </div>
            <HandTextViewer hand={selectedHand} isLoading={handLoadState === "loading"} />
          </section>
        </div>

        <aside className="coach-preview" aria-label="AI coach preview">
          <CoachPanel
            actionLabel="Ask coach"
            canRun={canRunCoach}
            disabledReason={coachDisabledReason}
            error={coachError}
            isLoading={coachLoading}
            onRun={reviewSelectedHand}
            result={coachResult}
          />
        </aside>
      </div>
    </div>
  );
}
