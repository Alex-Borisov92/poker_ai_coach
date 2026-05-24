from pydantic import BaseModel, Field

from poker_ai_coach.models.hands import HandSummary


class TournamentSummary(BaseModel):
    tournament_number: str
    first_hand_date: str | None = None
    last_hand_date: str | None = None
    is_date_unknown: bool = False
    buyin_in_cents: int | None = None
    rake_in_cents: int | None = None
    bounty_in_cents: int | None = None
    entrants: int | None = None
    hand_count: int = 0
    error_count: int = 0


class TournamentList(BaseModel):
    configured: bool
    connected: bool
    database_name: str | None = None
    tournaments: list[TournamentSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class TournamentHands(BaseModel):
    configured: bool
    connected: bool
    tournament_number: str
    database_name: str | None = None
    hands: list[HandSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
