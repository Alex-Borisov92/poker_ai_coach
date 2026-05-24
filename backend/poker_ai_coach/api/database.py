from pathlib import Path

from fastapi import APIRouter

from poker_ai_coach.config import get_settings, set_runtime_hm3_db_path
from poker_ai_coach.db.error_messages import (
    database_open_failure,
    missing_database_path_warning,
    missing_tables_warning,
)
from poker_ai_coach.db.hm3_connection import connect_readonly
from poker_ai_coach.db.schema_overview import build_schema_overview, create_explorer_snapshot
from poker_ai_coach.db.schema_probe import EXPECTED_TABLES, probe_schema
from poker_ai_coach.models.database import (
    DatabasePathRequest,
    DatabaseStatus,
    ExplorerSnapshotResponse,
    SchemaOverviewResponse,
)

router = APIRouter(prefix="/api/database", tags=["database"])


@router.get("/status", response_model=DatabaseStatus)
def database_status() -> DatabaseStatus:
    settings = get_settings()
    database_path = settings.hm3_db_path

    if database_path is None:
        return DatabaseStatus(
            configured=False,
            connected=False,
            expected_tables=EXPECTED_TABLES,
            warnings=[missing_database_path_warning()],
        )

    database_name = Path(database_path).name

    try:
        with connect_readonly(database_path) as connection:
            tables, table_counts, missing_tables = probe_schema(connection)
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return DatabaseStatus(
            configured=True,
            connected=False,
            database_name=database_name,
            expected_tables=EXPECTED_TABLES,
            warnings=warnings,
            error=error,
        )

    warnings = []
    if missing_tables:
        warnings.append(missing_tables_warning(missing_tables))

    return DatabaseStatus(
        configured=True,
        connected=True,
        database_name=database_name,
        tables=tables,
        table_counts=table_counts,
        expected_tables=EXPECTED_TABLES,
        missing_tables=missing_tables,
        warnings=warnings,
    )


@router.get("/schema-overview", response_model=SchemaOverviewResponse)
def schema_overview() -> SchemaOverviewResponse:
    return SchemaOverviewResponse.model_validate(build_schema_overview(get_settings()))


@router.post("/explorer-snapshot", response_model=ExplorerSnapshotResponse)
def explorer_snapshot() -> ExplorerSnapshotResponse:
    return ExplorerSnapshotResponse.model_validate(create_explorer_snapshot(get_settings()))


@router.post("/path", response_model=DatabaseStatus)
def set_database_path(request: DatabasePathRequest) -> DatabaseStatus:
    database_path = Path(request.database_path).expanduser()
    database_name = database_path.name

    try:
        with connect_readonly(database_path) as connection:
            tables, table_counts, missing_tables = probe_schema(connection)
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return DatabaseStatus(
            configured=True,
            connected=False,
            database_name=database_name,
            expected_tables=EXPECTED_TABLES,
            warnings=warnings,
            error=error,
        )

    set_runtime_hm3_db_path(database_path)
    warnings = ["Database path was loaded for this backend session only."]
    if missing_tables:
        warnings.append(missing_tables_warning(missing_tables))

    return DatabaseStatus(
        configured=True,
        connected=True,
        database_name=database_name,
        tables=tables,
        table_counts=table_counts,
        expected_tables=EXPECTED_TABLES,
        missing_tables=missing_tables,
        warnings=warnings,
    )
