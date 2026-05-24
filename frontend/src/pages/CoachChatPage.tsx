import { useEffect, useMemo, useState, type FormEvent } from "react";

import {
  createTrainingRun,
  fetchHandDetail,
  fetchHealthStatus,
  fetchTrainingRuns,
  sendAgentChat,
  type AgentChatResponse,
  type AgentToolStep,
  type HandDetail,
  type HealthStatus,
  type TrainingRunSummary,
} from "../api/client";
import { CoachAnswer } from "../components/CoachAnswer";

type LoadState = "loading" | "ready" | "error";
type ChatMessage = {
  role: "user" | "coach";
  content: string;
  toolSteps?: AgentToolStep[];
  selectedHandIds?: number[];
};
type ChatSession = {
  id: string;
  title: string;
  createdAt: string;
  responseSessionId: string | null;
  messages: ChatMessage[];
};
type ChatState = {
  activeId: string;
  sessions: ChatSession[];
};

const HISTORY_KEY = "poker-ai-coach-chat-sessions";
const OLD_STORAGE_KEY = "poker-ai-coach-agent-chat-history";
const OLD_SESSION_KEY = "poker-ai-coach-agent-session-id";

export function CoachChatPage() {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isStartingTraining, setIsStartingTraining] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [chatState, setChatState] = useState<ChatState>(() => readStoredChatState());
  const [trainingRuns, setTrainingRuns] = useState<TrainingRunSummary[]>([]);
  const [selectedHand, setSelectedHand] = useState<HandDetail | null>(null);

  const activeSession = useMemo(
    () => chatState.sessions.find((session) => session.id === chatState.activeId),
    [chatState],
  );
  const messages = activeSession?.messages ?? [];

  useEffect(() => {
    let isActive = true;

    async function loadStatus() {
      try {
        const healthData = await fetchHealthStatus();
        if (!isActive) {
          return;
        }
        setHealthStatus(healthData);
        const runs = await fetchTrainingRuns();
        if (!isActive) {
          return;
        }
        setTrainingRuns(runs.training_runs);
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

  useEffect(() => {
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(chatState.sessions.slice(0, 20)));
  }, [chatState.sessions]);

  const aiReady = Boolean(healthStatus?.ai_enabled && healthStatus.ai_configured);
  const canSend = Boolean(aiReady && question.trim() && !isSending);
  const disabledReason = useMemo(() => {
    if (loadState === "loading") {
      return "Loading coach status.";
    }
    if (isSending) {
      return "Agent is exploring the database with safe read-only tools.";
    }
    if (!healthStatus?.ai_enabled) {
      return "AI is disabled. Set AI_ENABLED=true and configure OPENAI_API_KEY to use the agent.";
    }
    if (!healthStatus.ai_configured) {
      return "OPENAI_API_KEY is missing. No report data will be sent.";
    }
    if (!question.trim()) {
      return "Ask about leaks, hands, stats, tournament patterns, or your next study focus.";
    }
    return "";
  }, [healthStatus, isSending, loadState, question]);
  const chatStatus = loadState === "loading" ? "Loading" : aiReady ? "Ready" : "Disabled";
  const statusClass = chatStatus === "Ready" ? "status-pill good" : "status-pill warning";

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAgent(question.trim());
  }

  async function runAgent(message: string) {
    if (!message || !aiReady || isSending || !activeSession) {
      return;
    }

    const currentSessionId = activeSession.id;
    const currentResponseSessionId = activeSession.responseSessionId;
    setChatState((current) =>
      updateSession(current, currentSessionId, (session) => ({
        ...session,
        title: session.messages.length ? session.title : titleFromMessage(message),
        messages: [...session.messages, { role: "user", content: message }],
      })),
    );
    setQuestion("");
    setChatError(null);
    setIsSending(true);
    try {
      const response = await sendAgentChat({
        message,
        session_id: currentResponseSessionId,
        mode: "coach_overview",
      });
      setChatState((current) =>
        updateSession(current, currentSessionId, (session) => ({
          ...session,
          responseSessionId: response.session_id,
          messages: [...session.messages, agentResponseToMessage(response)],
        })),
      );
    } catch (loadError) {
      setChatError(loadError instanceof Error ? loadError.message : "Agent chat failed");
    } finally {
      setIsSending(false);
    }
  }

  async function startTraining() {
    if (isStartingTraining) {
      return;
    }
    setIsStartingTraining(true);
    setChatError(null);
    try {
      const response = await createTrainingRun();
      if (response.error) {
        setChatError(response.error);
      }
      const runs = await fetchTrainingRuns();
      setTrainingRuns(runs.training_runs);
      if (response.training_run) {
        const message = [
          "Training started.",
          response.training_run.initial_summary,
          "",
          "You can now ask: find my top 5 leaks from the latest month.",
        ].join("\n");
        setChatState((current) =>
          updateSession(current, current.activeId, (session) => ({
            ...session,
            title: "Training " + formatChatDate(response.training_run!.created_at),
            messages: [...session.messages, { role: "coach", content: message }],
          })),
        );
      }
    } catch (loadError) {
      setChatError(loadError instanceof Error ? loadError.message : "Training start failed");
    } finally {
      setIsStartingTraining(false);
    }
  }

  async function openHand(handId: number) {
    try {
      const detail = await fetchHandDetail(handId);
      setSelectedHand(detail);
    } catch (loadError) {
      setChatError(loadError instanceof Error ? loadError.message : "Could not load hand");
    }
  }

  function startNewChat() {
    const session = createChatSession();
    setChatState((current) => ({
      activeId: session.id,
      sessions: [session, ...current.sessions],
    }));
    setQuestion("");
    setChatError(null);
  }

  function clearHistory() {
    const session = createChatSession();
    setChatState({ activeId: session.id, sessions: [session] });
    setChatError(null);
    window.localStorage.removeItem(HISTORY_KEY);
    window.localStorage.removeItem(OLD_STORAGE_KEY);
    window.localStorage.removeItem(OLD_SESSION_KEY);
  }

  return (
    <div className="coach-workspace">
      <aside className="chat-history-panel" aria-label="Chat history">
        <div className="panel-header">
          <h2>Trainings</h2>
          <button
            className="small-action"
            disabled={isStartingTraining}
            onClick={startTraining}
            type="button"
          >
            {isStartingTraining ? "Starting" : "Start"}
          </button>
        </div>
        <div className="training-history-list">
          {trainingRuns.length ? (
            trainingRuns.map((run) => (
              <div className="training-history-item" key={run.id}>
                <strong>{formatChatDate(run.created_at)}</strong>
                <span>{run.total_hands.toLocaleString()} hands</span>
                <small>{run.database_name ?? "database"}</small>
              </div>
            ))
          ) : (
            <p className="empty-state">No trainings yet.</p>
          )}
        </div>
        <div className="panel-header compact-header">
          <h2>Chats</h2>
          <button className="small-action" onClick={startNewChat} type="button">
            New
          </button>
        </div>
        <div className="chat-history-list">
          {chatState.sessions.map((session) => (
            <button
              className={session.id === chatState.activeId ? "chat-history-item active" : "chat-history-item"}
              key={session.id}
              onClick={() => setChatState((current) => ({ ...current, activeId: session.id }))}
              type="button"
            >
              <span>{session.title}</span>
              <small>{formatChatDate(session.createdAt)}</small>
            </button>
          ))}
        </div>
        <button className="small-action full-width" onClick={clearHistory} type="button">
          Clear history
        </button>
      </aside>

      <div className="page coach-page">
        <header className="page-header">
          <div>
            <h1>AI Coach</h1>
            <p>Ask for post-session microstakes MTT insights. The agent chooses tools when needed.</p>
          </div>
          <div className={statusClass}>{chatStatus}</div>
        </header>

        <div className="coach-main-layout">
          <div className="overview-main">
            {loadState === "loading" ? (
              <section className="panel loading-panel">
                <h2>Loading coach</h2>
                <p>Checking AI status and local report access.</p>
              </section>
            ) : null}

            {loadState === "error" ? (
              <section className="panel error-panel">
                <h2>Backend unavailable</h2>
                <p>{error}</p>
                <ul className="recovery-list">
                  <li>Start the backend with uvicorn.</li>
                  <li>Check VITE_API_BASE_URL if you use a custom API port.</li>
                  <li>Reload this page after backend restarts.</li>
                </ul>
              </section>
            ) : null}

            <section className="panel chat-panel">
              <div className="panel-header">
                <h2>Coach agent</h2>
                <span>{messages.length} messages in this chat</span>
              </div>
              <div className="chat-messages">
                {messages.length ? (
                  messages.map((message, index) => (
                    <article
                      className={`chat-message ${message.role}`}
                      key={`${message.role}-${index}`}
                    >
                      <strong>{message.role === "user" ? "You" : "Coach"}</strong>
                      {message.role === "coach" ? (
                        <CoachAnswer content={message.content} />
                      ) : (
                        <pre>{message.content}</pre>
                      )}
                      {message.selectedHandIds?.length ? (
                        <div className="selected-hands-strip">
                          <span>Hands</span>
                          {message.selectedHandIds.map((handId) => (
                            <button
                              className="hand-chip"
                              key={handId}
                              onClick={() => void openHand(handId)}
                              type="button"
                            >
                              {handId}
                            </button>
                          ))}
                        </div>
                      ) : null}
                      {message.toolSteps?.length ? <AgentSteps steps={message.toolSteps} /> : null}
                    </article>
                  ))
                ) : (
                  <p className="empty-state">
                    Ask: find my top leaks, give me a coach overview, choose hands to review,
                    or build a study plan from my database.
                  </p>
                )}
              </div>
              <form className="chat-form" onSubmit={submitQuestion}>
                <textarea
                  maxLength={2000}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Ask your coach"
                  value={question}
                />
                <div className="chat-actions">
                  <button className="primary-action" disabled={!canSend} type="submit">
                    {isSending ? "Thinking..." : "Send"}
                  </button>
                </div>
              </form>
              {chatError ? (
                <div className="coach-result error-panel">
                  <strong>Error</strong>
                  <p>{chatError}</p>
                </div>
              ) : null}
            </section>
          </div>

          <aside className="coach-preview" aria-label="Coach scope">
            <section className="panel coach-panel">
              <div className="panel-header">
                <h2>Agent scope</h2>
                <span>{healthStatus?.ai_configured ? "Configured" : "Limited"}</span>
              </div>
              <p>
                {aiReady
                  ? "The agent can inspect safe local reports and selected historical hands when the question needs it."
                  : disabledReason}
              </p>
              <div className="coach-preview-list">
                <span>Current training</span>
                <p>
                  {trainingRuns[0]
                    ? `${trainingRuns[0].total_hands.toLocaleString()} hands, ${trainingRuns[0].leak_count} leaks saved.`
                    : "Start a training to save coach snapshots and leak status."}
                </p>
                <span>Focus</span>
                <p>Leaks, all-ins, large pots, tournament clusters, and study drills.</p>
                <span>Limits</span>
                <p>No raw SQL, no DB writes, no full database upload, no active-hand advice.</p>
              </div>
            </section>
            {selectedHand ? (
              <section className="panel coach-panel">
                <div className="panel-header">
                  <h2>Hand {selectedHand.hand_id}</h2>
                  <button
                    className="small-action"
                    onClick={() => setSelectedHand(null)}
                    type="button"
                  >
                    Close
                  </button>
                </div>
                <pre className="hand-text compact-hand-text">
                  {selectedHand.hand_text || selectedHand.error || "No hand text."}
                </pre>
              </section>
            ) : null}
          </aside>
        </div>

      </div>
    </div>
  );
}

function AgentSteps({ steps }: { steps: AgentToolStep[] }) {
  return (
    <details className="agent-steps">
      <summary>Agent steps ({steps.length})</summary>
      <ol>
        {steps.map((step, index) => (
          <li key={`${step.name}-${index}`}>
            <span>{step.name}</span>
            <p>{step.summary}</p>
          </li>
        ))}
      </ol>
    </details>
  );
}

function readStoredChatState(): ChatState {
  const sessions = readStoredSessions();
  if (sessions.length) {
    return { activeId: sessions[0].id, sessions };
  }
  const session = createChatSession();
  return { activeId: session.id, sessions: [session] };
}

function readStoredSessions(): ChatSession[] {
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as ChatSession[];
      if (Array.isArray(parsed)) {
        return parsed.filter(isValidSession);
      }
    }
    const oldMessages = readOldMessages();
    if (oldMessages.length) {
      return [
        {
          id: crypto.randomUUID(),
          title: "Previous chat",
          createdAt: new Date().toISOString(),
          responseSessionId: window.localStorage.getItem(OLD_SESSION_KEY),
          messages: oldMessages,
        },
      ];
    }
  } catch {
    return [];
  }
  return [];
}

function readOldMessages(): ChatMessage[] {
  const raw = window.localStorage.getItem(OLD_STORAGE_KEY);
  if (!raw) {
    return [];
  }
  const parsed = JSON.parse(raw) as ChatMessage[];
  if (!Array.isArray(parsed)) {
    return [];
  }
  return parsed.filter(
    (message) =>
      (message.role === "user" || message.role === "coach") &&
      typeof message.content === "string",
  );
}

function isValidSession(session: ChatSession): boolean {
  return (
    typeof session.id === "string" &&
    typeof session.title === "string" &&
    typeof session.createdAt === "string" &&
    Array.isArray(session.messages)
  );
}

function createChatSession(): ChatSession {
  const createdAt = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: formatChatDate(createdAt),
    createdAt,
    responseSessionId: null,
    messages: [],
  };
}

function updateSession(
  state: ChatState,
  sessionId: string,
  updater: (session: ChatSession) => ChatSession,
): ChatState {
  return {
    ...state,
    sessions: state.sessions.map((session) =>
      session.id === sessionId ? updater(session) : session,
    ),
  };
}

function titleFromMessage(message: string): string {
  const trimmed = message.trim().replace(/\s+/g, " ");
  if (!trimmed) {
    return formatChatDate(new Date().toISOString());
  }
  return trimmed.length > 34 ? `${trimmed.slice(0, 34)}...` : trimmed;
}

function formatChatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  }).format(new Date(value));
}

function agentResponseToMessage(response: AgentChatResponse): ChatMessage {
  const warnings = response.warnings.length
    ? `\n\nWarnings:\n${response.warnings.map((warning) => `- ${warning}`).join("\n")}`
    : "";
  const content = response.error ? `Error: ${response.error}` : `${response.content}${warnings}`;
  return {
    role: "coach",
    content,
    toolSteps: response.tool_steps,
    selectedHandIds: response.selected_hand_ids,
  };
}
