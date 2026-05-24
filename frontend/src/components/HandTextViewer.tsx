import type { HandDetail } from "../api/client";

type HandTextViewerProps = {
  hand: HandDetail | null;
  isLoading: boolean;
};

export function HandTextViewer({ hand, isLoading }: HandTextViewerProps) {
  if (isLoading) {
    return <p className="empty-state">Loading hand text.</p>;
  }

  if (!hand) {
    return <p className="empty-state">Select a hand to read the history.</p>;
  }

  if (hand.error) {
    return <p className="empty-state">{hand.error}</p>;
  }

  return <pre className="hand-text">{hand.hand_text}</pre>;
}
