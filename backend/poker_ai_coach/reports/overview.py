import sqlite3
from pathlib import Path

from poker_ai_coach.config import Settings
from poker_ai_coach.db.error_messages import (
    database_open_failure,
    missing_database_path_warning,
    missing_tables_warning,
)
from poker_ai_coach.db.hm3_connection import connect_readonly
from poker_ai_coach.db.schema_probe import EXPECTED_TABLES, count_table_rows, list_tables
from poker_ai_coach.models.reports import DateRange, OverviewReport
from poker_ai_coach.reports.hero_aliases import hero_aliases

DATE_TABLE = "handhistories"
DATE_COLUMN = "handtimestamp"
MANY_INVALID_DATES_MIN_COUNT = 10


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({quote_known_identifier(table_name)})").fetchall()
    return {row["name"] for row in rows}


def quote_known_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def safe_count(connection: sqlite3.Connection, tables: set[str], table_name: str) -> int:
    if table_name not in tables:
        return 0
    return count_table_rows(connection, table_name)


def find_hero(connection: sqlite3.Connection, tables: set[str], hero_name: str) -> str | None:
    if "players" not in tables:
        return None

    columns = table_columns(connection, "players")
    if "playername" not in columns:
        return None

    for alias in hero_aliases(hero_name):
        row = connection.execute(
            """
            SELECT playername
            FROM players
            WHERE playername = ? COLLATE NOCASE
            LIMIT 1
            """,
            (alias,),
        ).fetchone()
        if row is not None:
            return str(row["playername"])
    return None


def get_date_coverage(
    connection: sqlite3.Connection, tables: set[str]
) -> tuple[DateRange, int, int, list[str]]:
    warnings = []
    if DATE_TABLE not in tables:
        return DateRange(), 0, 0, warnings

    columns = table_columns(connection, DATE_TABLE)
    if DATE_COLUMN not in columns:
        warnings.append("handhistories.handtimestamp is missing.")
        return DateRange(), 0, 0, warnings

    invalid_row = connection.execute(
        """
        SELECT COUNT(*) AS row_count
        FROM handhistories
        WHERE date(handtimestamp) = '1970-01-01'
           OR substr(CAST(handtimestamp AS TEXT), 1, 10) = '1970-01-01'
        """
    ).fetchone()
    invalid_count = int(invalid_row["row_count"])

    range_row = connection.execute(
        """
        SELECT
            MIN(date(handtimestamp)) AS start_date,
            MAX(date(handtimestamp)) AS end_date,
            COUNT(*) AS row_count
        FROM handhistories
        WHERE date(handtimestamp) IS NOT NULL
          AND date(handtimestamp) != '1970-01-01'
        """
    ).fetchone()
    date_range = DateRange(start=range_row["start_date"], end=range_row["end_date"])
    valid_count = int(range_row["row_count"])
    return date_range, valid_count, invalid_count, warnings


def build_overview_report(settings: Settings) -> OverviewReport:
    database_path = settings.hm3_db_path
    if database_path is None:
        return OverviewReport(
            configured=False,
            connected=False,
            hero_name=settings.hero_name,
            missing_tables=EXPECTED_TABLES,
            warnings=[missing_database_path_warning()],
        )

    database_name = Path(database_path).name

    try:
        with connect_readonly(database_path) as connection:
            return build_connected_overview(connection, database_name, settings.hero_name)
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return OverviewReport(
            configured=True,
            connected=False,
            database_name=database_name,
            hero_name=settings.hero_name,
            warnings=warnings,
            error=error,
        )


def build_connected_overview(
    connection: sqlite3.Connection, database_name: str, hero_name: str
) -> OverviewReport:
    tables = set(list_tables(connection))
    missing_tables = [table_name for table_name in EXPECTED_TABLES if table_name not in tables]

    total_hands = safe_count(connection, tables, "handhistories")
    tournaments = safe_count(connection, tables, "tournaments")
    imported_files = safe_count(connection, tables, "imported_files")
    error_hands = safe_count(connection, tables, "error_hands")
    matched_hero_name = find_hero(connection, tables, hero_name)
    hero_found = matched_hero_name is not None
    valid_date_range, valid_date_count, invalid_count, date_warnings = get_date_coverage(
        connection, tables
    )

    warnings = list(date_warnings)
    if missing_tables:
        warnings.append(missing_tables_warning(missing_tables))
    if "players" in tables and not hero_found:
        warnings.append(
            f"Hero '{hero_name}' was not found in players. Fallback alias 'hero' was also missing."
        )
    if invalid_count:
        warnings.append("Some hand dates are 1970-01-01 and were treated as unknown.")
    if invalid_count >= MANY_INVALID_DATES_MIN_COUNT and invalid_count >= valid_date_count:
        warnings.append("Many hand dates are invalid, so date coverage may be incomplete.")
    if total_hands and valid_date_count == 0:
        warnings.append("No valid hand dates were found.")
    if total_hands == 0 and tournaments == 0 and imported_files == 0 and error_hands == 0:
        warnings.append("Database looks empty for overview tables.")

    return OverviewReport(
        configured=True,
        connected=True,
        database_name=database_name,
        hero_name=hero_name,
        hero_found=hero_found,
        total_hands=total_hands,
        tournaments=tournaments,
        imported_files=imported_files,
        error_hands=error_hands,
        valid_date_range=valid_date_range,
        valid_date_count=valid_date_count,
        invalid_1970_date_count=invalid_count,
        missing_tables=missing_tables,
        warnings=warnings,
    )
