import type { CoachResponse } from "../api/client";
import { CoachAnswer } from "./CoachAnswer";

type CoachPanelProps = {
  title?: string;
  actionLabel: string;
  canRun: boolean;
  disabledReason: string;
  isLoading: boolean;
  error: string | null;
  result: CoachResponse | null;
  onRun: () => void;
};

export function CoachPanel({
  title = "AI Coach",
  actionLabel,
  canRun,
  disabledReason,
  isLoading,
  error,
  result,
  onRun,
}: CoachPanelProps) {
  const status = canRun ? "Ready" : "Disabled";

  return (
    <div className="panel coach-panel">
      <div className="panel-header">
        <h2>{title}</h2>
        <span>{status}</span>
      </div>
      <p>{canRun ? "Coach can review this historical data." : disabledReason}</p>
      <button
        className="primary-action full-width"
        disabled={!canRun || isLoading}
        onClick={onRun}
        type="button"
      >
        {isLoading ? "Reviewing..." : actionLabel}
      </button>

      {error ? (
        <div className="coach-result error-panel">
          <strong>Error</strong>
          <p>{error}</p>
        </div>
      ) : null}

      {result?.warnings.length ? (
        <div className="coach-result warning-panel">
          <strong>Warnings</strong>
          <ul>
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {result?.content ? (
        <div className="coach-result">
          <strong>Coach response</strong>
          <CoachAnswer content={result.content} />
        </div>
      ) : null}
    </div>
  );
}
