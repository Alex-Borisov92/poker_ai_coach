from pydantic import BaseModel, Field


class DatabasePathRequest(BaseModel):
    database_path: str


class DatabaseStatus(BaseModel):
    configured: bool
    connected: bool
    database_name: str | None = None
    tables: list[str] = Field(default_factory=list)
    table_counts: dict[str, int] = Field(default_factory=dict)
    expected_tables: list[str] = Field(default_factory=list)
    missing_tables: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class SchemaColumn(BaseModel):
    name: str
    type: str = ""
    not_null: bool = False
    primary_key: bool = False


class SchemaTable(BaseModel):
    name: str
    row_count: int
    columns: list[SchemaColumn] = Field(default_factory=list)
    role: str
    contains_sensitive_text: bool = False


class SchemaRelationship(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    note: str


class StatMapping(BaseModel):
    metric: str
    formula: str
    source_table: str
    confidence: str


class SchemaOverviewResponse(BaseModel):
    configured: bool
    connected: bool
    database_name: str | None = None
    tables: list[SchemaTable] = Field(default_factory=list)
    relationships: list[SchemaRelationship] = Field(default_factory=list)
    stat_mappings: list[StatMapping] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class ExplorerSnapshotResponse(BaseModel):
    created: bool
    database_name: str | None = None
    snapshot_name: str | None = None
    relative_path: str | None = None
    tables: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
