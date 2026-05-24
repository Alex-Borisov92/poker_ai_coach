from pydantic import BaseModel, Field


class StudyFocusArea(BaseModel):
    title: str
    evidence: str
    confidence: str
    action: str


class StudyHand(BaseModel):
    hand_id: int
    tournament_number: str | None = None
    hand_date: str | None = None
    reasons: list[str] = Field(default_factory=list)
    source: str


class StudyPlan(BaseModel):
    configured: bool
    connected: bool
    database_name: str | None = None
    hero_name: str
    focus_areas: list[StudyFocusArea] = Field(default_factory=list)
    hands_to_review: list[StudyHand] = Field(default_factory=list)
    drills: list[str] = Field(default_factory=list)
    weekly_checklist: list[str] = Field(default_factory=list)
    confidence: str = "low"
    missing_data: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
