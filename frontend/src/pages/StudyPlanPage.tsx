import { useEffect, useState } from "react";

import {
  fetchHealthStatus,
  fetchStudyPlan,
  startDeepAnalysis,
  type DeepAnalysisJob,
  type HealthStatus,
  type StudyPlan,
} from "../api/client";
import { CoachAnswer } from "../components/CoachAnswer";

type LoadState = "loading" | "ready" | "error";

const studyPrompt =
  "Build my weekly study plan as a microstakes MTT coach. Use HM3 stats, leak hypotheses, selected hands, and coaching principles.";

export function StudyPlanPage() {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [deepResult, setDeepResult] = useState<DeepAnalysisJob | null>(null);
  const [fallbackPlan, setFallbackPlan] = useState<StudyPlan | null>(null);
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
          void runDeepPlan();
        } else {
          const plan = await fetchStudyPlan();
          if (isActive) {
            setFallbackPlan(plan);
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

  async function runDeepPlan() {
    setIsRunning(true);
    setError(null);
    try {
      const result = await startDeepAnalysis({
        message: studyPrompt,
        mode: "study_plan_deep",
        limit: 10,
      });
      setDeepResult(result);
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
          <h1>Study Plan</h1>
          <p>AI coach weekly plan from stats, leak hypotheses, and review hands.</p>
        </div>
        <button
          className="primary-action"
          disabled={!canRunAgent || isRunning}
          onClick={runDeepPlan}
          type="button"
        >
          {isRunning ? "Building plan..." : "Build deep plan"}
        </button>
      </header>

      {loadState === "loading" || isRunning ? (
        <section className="panel loading-panel">
          <h2>Coach is building the plan</h2>
          <p>Using safe local reports and selected historical hands.</p>
        </section>
      ) : null}

      {loadState === "error" || error ? (
        <section className="panel error-panel">
          <h2>Study Plan unavailable</h2>
          <p>{error}</p>
        </section>
      ) : null}

      {!canRunAgent && loadState === "ready" ? (
        <section className="panel warning-panel">
          <h2>AI coach is not enabled</h2>
          <p>
            Enable AI in backend config to generate a coach study plan. Below is only a local
            fallback plan.
          </p>
        </section>
      ) : null}

      {deepResult ? <DeepPlan result={deepResult} /> : null}

      {!deepResult && fallbackPlan ? <FallbackPlan plan={fallbackPlan} /> : null}
    </div>
  );
}

function DeepPlan({ result }: { result: DeepAnalysisJob }) {
  return (
    <div className="study-plan-layout">
      <section className="panel">
        <div className="panel-header">
          <h2>Focus areas</h2>
          <span>{result.study_items.length} drills</span>
        </div>
        <div className="study-card-list">
          {result.study_items.map((item) => (
            <article className="study-card" key={item.title}>
              <div className="panel-header">
                <h3>{item.title}</h3>
                <span>{item.status}</span>
              </div>
              <p>{item.drill}</p>
              <ul>
                {item.checklist.map((check) => (
                  <li key={check}>{check}</li>
                ))}
              </ul>
              {item.linked_hand_ids.length ? (
                <div className="selected-hands-strip">
                  <span>Hands</span>
                  {item.linked_hand_ids.map((handId) => (
                    <code key={handId}>{handId}</code>
                  ))}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      </section>
      <section className="panel chat-panel">
        <div className="panel-header">
          <h2>Coach notes</h2>
          <span>{result.status}</span>
        </div>
        <div className="chat-message assistant">
          <CoachAnswer content={result.content || "Coach returned an empty answer."} />
        </div>
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
    </div>
  );
}

function FallbackPlan({ plan }: { plan: StudyPlan }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Fallback plan</h2>
        <span>{plan.confidence}</span>
      </div>
      <div className="study-grid">
        <div>
          <h2>Focus areas</h2>
          <ul>
            {plan.focus_areas.map((area) => (
              <li key={area.title}>{area.title}</li>
            ))}
          </ul>
        </div>
        <div>
          <h2>Weekly checklist</h2>
          <ul>
            {plan.weekly_checklist.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
