from pydantic import BaseModel, Field


class TrainingLeak(BaseModel):
    id: int | None = None
    training_run_id: int | None = None
    leak_key: str
    title: str
    severity: str
    status: str = "open"
    evidence: str
    coach_read: str
    sample_size: int = 0
    related_hand_ids: list[int] = Field(default_factory=list)
    confidence: str = "medium"


class TrainingStudyItem(BaseModel):
    id: int | None = None
    training_run_id: int | None = None
    title: str
    drill: str
    checklist: list[str] = Field(default_factory=list)
    linked_leak_keys: list[str] = Field(default_factory=list)
    linked_hand_ids: list[int] = Field(default_factory=list)
    status: str = "open"


class TrainingRunSummary(BaseModel):
    id: int
    created_at: str
    database_name: str | None = None
    hero_name: str
    model: str | None = None
    total_hands: int = 0
    max_hand_id: int | None = None
    latest_valid_month: str | None = None
    initial_summary: str = ""
    leak_count: int = 0
    study_item_count: int = 0


class TrainingRunDetail(TrainingRunSummary):
    valid_hand_count: int = 0
    invalid_1970_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    leaks: list[TrainingLeak] = Field(default_factory=list)
    study_items: list[TrainingStudyItem] = Field(default_factory=list)
    deep_leak_result: str = ""
    study_plan_result: str = ""


class TrainingRunCreateResponse(BaseModel):
    created: bool
    training_run: TrainingRunDetail | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class TrainingRunList(BaseModel):
    training_runs: list[TrainingRunSummary] = Field(default_factory=list)


class TrainingCompareResponse(BaseModel):
    training_run_id: int
    previous_training_run_id: int | None = None
    new_hands: int = 0
    leak_changes: list[str] = Field(default_factory=list)
    study_plan_changes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
