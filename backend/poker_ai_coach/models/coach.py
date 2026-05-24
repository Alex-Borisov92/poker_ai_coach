from pydantic import BaseModel, Field


class HandReviewRequest(BaseModel):
    hand_id: int


class CoachChatContext(BaseModel):
    include_overview: bool = False
    include_leak_report: bool = False
    include_study_plan: bool = False
    hand_id: int | None = None


class CoachChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    context: CoachChatContext = Field(default_factory=CoachChatContext)


class CoachResponse(BaseModel):
    ai_enabled: bool
    ai_configured: bool
    provider: str
    model: str | None = None
    content: str = ""
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    mode: str = "coach_overview"


class AgentToolStep(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)
    summary: str


class AgentChatResponse(BaseModel):
    ai_enabled: bool
    ai_configured: bool
    provider: str
    model: str | None = None
    session_id: str
    content: str = ""
    tool_steps: list[AgentToolStep] = Field(default_factory=list)
    selected_hand_ids: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class DeepAnalysisRequest(BaseModel):
    message: str = Field(default="Find my main leaks and review concrete hands.", max_length=2000)
    mode: str = "leak_finder_deep"
    training_run_id: int | None = None
    period: str | None = None
    limit: int = Field(default=10, ge=1, le=10)


class DeepAnalysisJob(BaseModel):
    job_id: str
    status: str
    mode: str
    training_run_id: int | None = None
    content: str = ""
    leaks: list[dict] = Field(default_factory=list)
    hand_analyses: list[dict] = Field(default_factory=list)
    study_items: list[dict] = Field(default_factory=list)
    steps: list[AgentToolStep] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
