export type DatabaseStatus = {
  configured: boolean;
  connected: boolean;
  database_name: string | null;
  tables: string[];
  table_counts: Record<string, number>;
  expected_tables: string[];
  missing_tables: string[];
  warnings: string[];
  error: string | null;
};

export type HealthStatus = {
  status: string;
  app: string;
  version: string;
  hero_name: string;
  ai_enabled: boolean;
  ai_configured: boolean;
  ai_model: string | null;
};

export type OverviewReport = {
  configured: boolean;
  connected: boolean;
  database_name: string | null;
  hero_name: string;
  hero_found: boolean;
  total_hands: number;
  tournaments: number;
  imported_files: number;
  error_hands: number;
  valid_date_range: {
    start: string | null;
    end: string | null;
  };
  valid_date_count: number;
  invalid_1970_date_count: number;
  missing_tables: string[];
  warnings: string[];
  error: string | null;
};

export type LeakFinderItem = {
  leak_key: string;
  leak_name: string;
  evidence: string;
  confidence: "high" | "medium" | "low";
  recommended_action: string;
  related_hand_ids: number[];
  missing_data: string[];
};

export type LeakFinderReport = {
  configured: boolean;
  connected: boolean;
  database_name: string | null;
  hero_name: string;
  total_hands: number;
  leaks: LeakFinderItem[];
  missing_data: string[];
  warnings: string[];
  error: string | null;
};

export type HandSummary = {
  hand_id: number;
  tournament_number: string | null;
  hand_date: string | null;
  is_date_unknown: boolean;
  reasons: string[];
  source: string;
};

export type HandReviewQueue = {
  configured: boolean;
  connected: boolean;
  database_name: string | null;
  hands: HandSummary[];
  warnings: string[];
  error: string | null;
};

export type HandDetail = {
  configured: boolean;
  connected: boolean;
  hand_id: number | null;
  tournament_number: string | null;
  hand_date: string | null;
  is_date_unknown: boolean;
  source: string | null;
  hand_text: string;
  warnings: string[];
  error: string | null;
};

export type CoachResponse = {
  ai_enabled: boolean;
  ai_configured: boolean;
  provider: string;
  model: string | null;
  content: string;
  warnings: string[];
  error: string | null;
};

export type AgentToolStep = {
  name: string;
  arguments: Record<string, unknown>;
  summary: string;
};

export type AgentChatRequest = {
  message: string;
  session_id: string | null;
  mode?:
    | "coach_overview"
    | "database_scout"
    | "stats_overview"
    | "leak_finder"
    | "study_plan"
    | "hand_review"
    | "tournament_story"
    | "training_initial"
    | "training_followup"
    | "leak_finder_deep"
    | "study_plan_deep"
    | "hand_batch_review";
};

export type AgentChatResponse = {
  ai_enabled: boolean;
  ai_configured: boolean;
  provider: string;
  model: string | null;
  session_id: string;
  content: string;
  tool_steps: AgentToolStep[];
  selected_hand_ids: number[];
  warnings: string[];
  error: string | null;
};

export type CoachChatContext = {
  include_overview: boolean;
  include_leak_report: boolean;
  include_study_plan: boolean;
  hand_id: number | null;
};

export type CoachChatRequest = {
  message: string;
  context: CoachChatContext;
};

export type StudyFocusArea = {
  title: string;
  evidence: string;
  confidence: "high" | "medium" | "low";
  action: string;
};

export type StudyHand = {
  hand_id: number;
  tournament_number: string | null;
  hand_date: string | null;
  reasons: string[];
  source: string;
};

export type StudyPlan = {
  configured: boolean;
  connected: boolean;
  database_name: string | null;
  hero_name: string;
  focus_areas: StudyFocusArea[];
  hands_to_review: StudyHand[];
  drills: string[];
  weekly_checklist: string[];
  confidence: "high" | "medium" | "low";
  missing_data: string[];
  warnings: string[];
  error: string | null;
};

export type TournamentSummary = {
  tournament_number: string;
  first_hand_date: string | null;
  last_hand_date: string | null;
  is_date_unknown: boolean;
  buyin_in_cents: number | null;
  rake_in_cents: number | null;
  bounty_in_cents: number | null;
  entrants: number | null;
  hand_count: number;
  error_count: number;
};

export type TournamentList = {
  configured: boolean;
  connected: boolean;
  database_name: string | null;
  tournaments: TournamentSummary[];
  warnings: string[];
  error: string | null;
};

export type TournamentHands = {
  configured: boolean;
  connected: boolean;
  tournament_number: string;
  database_name: string | null;
  hands: HandSummary[];
  warnings: string[];
  error: string | null;
};

export type TournamentFilters = {
  dateFrom?: string;
  dateTo?: string;
  search?: string;
  onlyWithErrors?: boolean;
  limit?: number;
};

export type ExplorerSnapshotResponse = {
  created: boolean;
  database_name: string | null;
  snapshot_name: string | null;
  relative_path: string | null;
  tables: string[];
  warnings: string[];
  error: string | null;
};

export type TrainingLeak = {
  id: number | null;
  training_run_id: number | null;
  leak_key: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low";
  status: "open" | "improving" | "resolved";
  evidence: string;
  coach_read: string;
  sample_size: number;
  related_hand_ids: number[];
  confidence: "high" | "medium" | "low";
};

export type TrainingStudyItem = {
  id: number | null;
  training_run_id: number | null;
  title: string;
  drill: string;
  checklist: string[];
  linked_leak_keys: string[];
  linked_hand_ids: number[];
  status: "new" | "open" | "improving" | "done";
};

export type TrainingRunSummary = {
  id: number;
  created_at: string;
  database_name: string | null;
  hero_name: string;
  model: string | null;
  total_hands: number;
  max_hand_id: number | null;
  latest_valid_month: string | null;
  initial_summary: string;
  leak_count: number;
  study_item_count: number;
};

export type TrainingRunDetail = TrainingRunSummary & {
  valid_hand_count: number;
  invalid_1970_count: number;
  warnings: string[];
  leaks: TrainingLeak[];
  study_items: TrainingStudyItem[];
  deep_leak_result: string | null;
  study_plan_result: string | null;
};

export type TrainingRunCreateResponse = {
  created: boolean;
  training_run: TrainingRunDetail | null;
  warnings: string[];
  error: string | null;
};

export type TrainingRunList = {
  training_runs: TrainingRunSummary[];
};

export type TrainingCompareResponse = {
  current: TrainingRunDetail | null;
  previous: TrainingRunDetail | null;
  new_hands: number | null;
  changed_leaks: TrainingLeak[];
  warnings: string[];
};

export type DeepAnalysisRequest = {
  message: string;
  mode?: "leak_finder_deep" | "study_plan_deep" | "training_initial" | "training_followup";
  training_run_id?: number | null;
  period?: string | null;
  limit?: number;
};

export type DeepAnalysisJob = {
  job_id: string;
  status: "queued" | "running" | "completed" | "error";
  mode: string;
  training_run_id: number | null;
  content: string;
  leaks: TrainingLeak[];
  hand_analyses: HandActionAnalysis[];
  study_items: TrainingStudyItem[];
  steps: AgentToolStep[];
  warnings: string[];
  error: string | null;
};

export type HandActionAnalysis = {
  hand_id: number;
  tournament_number: string | null;
  hand_date: string | null;
  hero_position: string | null;
  hero_stack_bb: number | null;
  hero_cards_seen: boolean;
  hero_actions: string[];
  pot_size: number | null;
  coach_questions: string[];
  hand_text_excerpt: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers ?? {}),
      },
      ...options,
    });
  } catch {
    throw new Error(
      `Backend unavailable. Start FastAPI at ${API_BASE_URL} or set VITE_API_BASE_URL.`,
    );
  }
  if (!response.ok) {
    throw new Error(`Backend request failed with status ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export function fetchDatabaseStatus(): Promise<DatabaseStatus> {
  return requestJson<DatabaseStatus>("/api/database/status");
}

export function createExplorerSnapshot(): Promise<ExplorerSnapshotResponse> {
  return requestJson<ExplorerSnapshotResponse>("/api/database/explorer-snapshot", {
    method: "POST",
  });
}

export function setDatabasePath(databasePath: string): Promise<DatabaseStatus> {
  return requestJson<DatabaseStatus>("/api/database/path", {
    method: "POST",
    body: JSON.stringify({ database_path: databasePath }),
  });
}

export function fetchHealthStatus(): Promise<HealthStatus> {
  return requestJson<HealthStatus>("/api/health");
}

export function fetchOverviewReport(): Promise<OverviewReport> {
  return requestJson<OverviewReport>("/api/reports/overview");
}

export function fetchLeakFinderReport(): Promise<LeakFinderReport> {
  return requestJson<LeakFinderReport>("/api/reports/leak-finder");
}

export function fetchHandReviewQueue(limit = 50): Promise<HandReviewQueue> {
  return requestJson<HandReviewQueue>(`/api/hands/review-queue?limit=${limit}`);
}

export function fetchHandDetail(handId: number): Promise<HandDetail> {
  return requestJson<HandDetail>(`/api/hands/${handId}`);
}

export function fetchStudyPlan(): Promise<StudyPlan> {
  return requestJson<StudyPlan>("/api/study-plan");
}

export function fetchTournaments(filters: TournamentFilters = {}): Promise<TournamentList> {
  const params = new URLSearchParams();
  if (filters.dateFrom) {
    params.set("date_from", filters.dateFrom);
  }
  if (filters.dateTo) {
    params.set("date_to", filters.dateTo);
  }
  if (filters.search) {
    params.set("search", filters.search);
  }
  if (filters.onlyWithErrors) {
    params.set("only_with_errors", "true");
  }
  if (filters.limit) {
    params.set("limit", String(filters.limit));
  }
  const query = params.toString();
  return requestJson<TournamentList>(`/api/tournaments${query ? `?${query}` : ""}`);
}

export function fetchTournamentHands(
  tournamentNumber: string,
  limit = 100,
): Promise<TournamentHands> {
  return requestJson<TournamentHands>(
    `/api/tournaments/${encodeURIComponent(tournamentNumber)}/hands?limit=${limit}`,
  );
}

export function analyzeOverview(): Promise<CoachResponse> {
  return requestJson<CoachResponse>("/api/coach/analyze-overview", {
    method: "POST",
  });
}

export function analyzeLeaks(): Promise<CoachResponse> {
  return requestJson<CoachResponse>("/api/coach/analyze-leaks", {
    method: "POST",
  });
}

export function explainStudyPlan(): Promise<CoachResponse> {
  return requestJson<CoachResponse>("/api/coach/study-plan", {
    method: "POST",
  });
}

export function reviewHand(handId: number): Promise<CoachResponse> {
  return requestJson<CoachResponse>("/api/coach/review-hand", {
    method: "POST",
    body: JSON.stringify({ hand_id: handId }),
  });
}

export function sendCoachChat(request: CoachChatRequest): Promise<CoachResponse> {
  return requestJson<CoachResponse>("/api/coach/chat", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function sendAgentChat(request: AgentChatRequest): Promise<AgentChatResponse> {
  return requestJson<AgentChatResponse>("/api/coach/agent-chat", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function createTrainingRun(): Promise<TrainingRunCreateResponse> {
  return requestJson<TrainingRunCreateResponse>("/api/training-runs", {
    method: "POST",
  });
}

export function fetchTrainingRuns(): Promise<TrainingRunList> {
  return requestJson<TrainingRunList>("/api/training-runs");
}

export function fetchTrainingRun(trainingRunId: number): Promise<TrainingRunDetail> {
  return requestJson<TrainingRunDetail>(`/api/training-runs/${trainingRunId}`);
}

export function compareTrainingRun(trainingRunId: number): Promise<TrainingCompareResponse> {
  return requestJson<TrainingCompareResponse>(
    `/api/training-runs/${trainingRunId}/compare-latest`,
    {
      method: "POST",
    },
  );
}

export function startDeepAnalysis(request: DeepAnalysisRequest): Promise<DeepAnalysisJob> {
  return requestJson<DeepAnalysisJob>("/api/coach/deep-analysis", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function fetchDeepAnalysisJob(jobId: string): Promise<DeepAnalysisJob> {
  return requestJson<DeepAnalysisJob>(`/api/coach/jobs/${jobId}`);
}
