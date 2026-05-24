from pydantic import BaseModel, Field


class HandSummary(BaseModel):
    hand_id: int
    tournament_number: str | None = None
    hand_date: str | None = None
    is_date_unknown: bool = False
    reasons: list[str] = Field(default_factory=list)
    source: str


class HandReviewQueue(BaseModel):
    configured: bool
    connected: bool
    database_name: str | None = None
    hands: list[HandSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class HandDetail(BaseModel):
    configured: bool
    connected: bool
    hand_id: int | None = None
    tournament_number: str | None = None
    hand_date: str | None = None
    is_date_unknown: bool = False
    source: str | None = None
    hand_text: str = ""
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
