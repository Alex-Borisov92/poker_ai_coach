from pydantic import BaseModel, Field


class DateRange(BaseModel):
    start: str | None = None
    end: str | None = None


class OverviewReport(BaseModel):
    configured: bool
    connected: bool
    database_name: str | None = None
    hero_name: str
    hero_found: bool = False
    total_hands: int = 0
    tournaments: int = 0
    imported_files: int = 0
    error_hands: int = 0
    valid_date_range: DateRange = Field(default_factory=DateRange)
    valid_date_count: int = 0
    invalid_1970_date_count: int = 0
    missing_tables: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class LeakFinderItem(BaseModel):
    leak_key: str
    leak_name: str
    evidence: str
    confidence: str
    recommended_action: str
    related_hand_ids: list[int] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)


class LeakFinderReport(BaseModel):
    configured: bool
    connected: bool
    database_name: str | None = None
    hero_name: str
    total_hands: int = 0
    leaks: list[LeakFinderItem] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
