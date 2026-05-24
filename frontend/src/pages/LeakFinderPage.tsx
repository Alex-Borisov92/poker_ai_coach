import { useEffect, useState } from "react";

import {
  fetchHealthStatus,
  fetchLeakFinderReport,
  startDeepAnalysis,
  type DeepAnalysisJob,
  type HealthStatus,
  type LeakFinderReport,
  type TrainingLeak,
} from "../api/client";
import { CoachAnswer } from "../components/CoachAnswer";

type LoadState = "loading" | "ready" | "error";

const leakPrompt =
  "Find my main leaks as a microstakes MTT coach. Start from HM3 aggregate stats, then use selected hands only as evidence to review.";

export function LeakFinderPage() {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [deepResult, setDeepResult] = useState<DeepAnalysisJob | null>(null);
  const [fallbackReport, setFallbackReport] = useState<LeakFinderReport | null>(null);
  const [selectedLeakKey, setSelectedLeakKey] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function load() {
      try {
        const health = await fetchHealthStatus();
        if (!isActive) {
          return;
        }
        setHealthStatus(health);
        setLoadState("ready");
        if (health.ai_enabled && health.ai_configured) {
          void runDeepFinder();
        } else {
          const report = await fetchLeakFinderReport();
          if (isActive) {
            setFallbackReport(report);
          }
        }
      } catch (loadError) {
        if (!isActive) {
          return;
        }
        setLoadState("error");
        setError(loadError instanceof Error ? loadError.message : "Backend unavailable");
      }
    }

    load();

    return () => {
      isActive = false;
    };
  }, []);

  const canRunAgent = Boolean(healthStatus?.ai_enabled && healthStatus.ai_configured);

  async function runDeepFinder() {
    setIsRunning(true);
    setError(null);
    try {
      const result = await startDeepAnalysis({
        message: leakPrompt,
        mode: "leak_finder_deep",
        limit: 10,
      });
      setDeepResult(result);
      setSelectedLeakKey(result.leaks[0]?.leak_key ?? null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Coach request failed");
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Leak Finder</h1>
          <p>AI coach report from HM3 aggregate stats, safe context, and selected hands.</p>
        </div>
        <button
          className="primary-action"
          disabled={!canRunAgent || isRunning}
          onClick={runDeepFinder}
          type="button"
        >
          {isRunning ? "Finding leaks..." : "Run deep leak finder"}
        </button>
      </header>

      {loadState === "loading" || isRunning ? (
        <section className="panel loading-panel">
          <h2>Coach is checking the database</h2>
          <p>Stats first, hands second. No raw SQL and no HM3 writes.</p>
        </section>
      ) : null}

      {loadState === "error" || error ? (
        <section className="panel error-panel">
          <h2>Leak Finder unavailable</h2>
          <p>{error}</p>
        </section>
      ) : null}

      {!canRunAgent && loadState === "ready" ? (
        <section className="panel warning-panel">
          <h2>AI coach is not enabled</h2>
          <p>
            Enable AI in backend config to generate a coach leak report. Below is only a local
            fallback signal list.
          </p>
        </section>
      ) : null}

      {deepResult ? (
        <DeepLeakReport
          onSelectLeak={setSelectedLeakKey}
          result={deepResult}
          selectedLeakKey={selectedLeakKey}
        />
      ) : null}

      {!deepResult && fallbackReport ? (
        <section className="panel">
          <div className="panel-header">
            <h2>Fallback signals</h2>
            <span>{fallbackReport.leaks.length} signals</span>
          </div>
          {fallbackReport.leaks.length ? (
            <div className="leak-list">
              {fallbackReport.leaks.map((leak) => (
                <article className="leak-card" key={leak.leak_key}>
                  <div className="leak-card-header">
                    <h3>{leak.leak_name}</h3>
                    <span className={`confidence ${leak.confidence}`}>{leak.confidence}</span>
                  </div>
                  <p>{leak.evidence}</p>
                  <strong>Action</strong>
                  <p>{leak.recommended_action}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="empty-state">Not enough supported data to show leak signals.</p>
          )}
        </section>
      ) : null}
    </div>
  );
}

function DeepLeakReport({
  onSelectLeak,
  result,
  selectedLeakKey,
}: {
  onSelectLeak: (leakKey: string) => void;
  result: DeepAnalysisJob;
  selectedLeakKey: string | null;
}) {
  const selectedLeak = result.leaks.find((leak) => leak.leak_key === selectedLeakKey);
  const selectedHandIds = selectedLeak?.related_hand_ids ?? [];
  const relatedHands = result.hand_analyses.filter((hand) =>
    selectedHandIds.includes(Number(hand.hand_id)),
  );

  return (
    <section className="leak-workspace">
      <div className="leak-card-grid">
        {result.leaks.map((leak) => (
          <LeakCard
            isSelected={leak.leak_key === selectedLeakKey}
            key={leak.leak_key}
            leak={leak}
            onClick={() => onSelectLeak(leak.leak_key)}
          />
        ))}
      </div>
      <section className="panel chat-panel">
        <div className="panel-header">
          <h2>{selectedLeak?.title ?? "Coach leak report"}</h2>
          <span>{selectedLeak?.severity ?? result.status}</span>
        </div>
        <div className="chat-message assistant">
          <CoachAnswer content={result.content || "Coach returned an empty answer."} />
        </div>
        {relatedHands.length ? (
          <div className="hand-analysis-list">
            {relatedHands.map((hand) => (
              <article className="hand-analysis-card" key={hand.hand_id}>
                <div className="panel-header">
                  <h3>Hand {hand.hand_id}</h3>
                  <span>{hand.tournament_number ?? "no tournament"}</span>
                </div>
                <p>
                  Position {hand.hero_position ?? "unknown"}, stack{" "}
                  {hand.hero_stack_bb ?? "unknown"}bb, pot {hand.pot_size ?? "unknown"}.
                </p>
                <p>Hero line: {hand.hero_actions.join(", ") || "unknown"}</p>
                <ul>
                  {hand.coach_questions.map((question) => (
                    <li key={question}>{question}</li>
                  ))}
                </ul>
                <pre className="hand-excerpt">{hand.hand_text_excerpt}</pre>
              </article>
            ))}
          </div>
        ) : null}
        {result.warnings.length ? (
          <div className="coach-result warning-panel">
            <strong>Warnings</strong>
            <ul>
              {result.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {result.steps.length ? (
          <details className="agent-steps">
            <summary>Coach steps ({result.steps.length})</summary>
            <ol>
              {result.steps.map((step, index) => (
                <li key={`${step.name}-${index}`}>
                  <span>{step.name}</span>
                  <p>{step.summary}</p>
                </li>
              ))}
            </ol>
          </details>
        ) : null}
      </section>
    </section>
  );
}

function LeakCard({
  isSelected,
  leak,
  onClick,
}: {
  isSelected: boolean;
  leak: TrainingLeak;
  onClick: () => void;
}) {
  return (
    <button
      className={isSelected ? "deep-leak-card selected" : "deep-leak-card"}
      onClick={onClick}
      type="button"
    >
      <div className="leak-card-header">
        <h3>{leak.title}</h3>
        <span className={`severity-badge ${leak.severity}`}>{leak.severity}</span>
      </div>
      <p>{leak.evidence}</p>
      <small>
        {leak.confidence} confidence, {leak.sample_size.toLocaleString()} sample
      </small>
    </button>
  );
}
