import sqlite3
from pathlib import Path
from typing import Any

from poker_ai_coach.config import Settings
from poker_ai_coach.db.error_messages import database_open_failure, missing_database_path_warning
from poker_ai_coach.db.hm3_connection import connect_readonly
from poker_ai_coach.reports.hm3_player_stats import build_hm3_player_stats

SAFE_SNAPSHOT_TABLES = [
    "hm3_tables",
    "hm3_columns",
    "hm3_relationships",
    "hm3_stat_mappings",
    "hm3_table_counts",
    "hm3_metric_preview",
    "agent_tool_catalog",
]

KNOWN_RELATIONSHIPS = [
    {
        "source_table": "compiledplayerresults",
        "source_column": "player_id",
        "target_table": "players",
        "target_column": "player_id",
        "note": "Aggregate stats are linked to a player.",
    },
    {
        "source_table": "handhistories",
        "source_column": "tournament_number",
        "target_table": "tournaments",
        "target_column": "tournament_number",
        "note": "Historical hands can be grouped by tournament number.",
    },
    {
        "source_table": "tournament_players",
        "source_column": "player_id",
        "target_table": "players",
        "target_column": "player_id",
        "note": "Tournament result rows are linked to players.",
    },
    {
        "source_table": "tournament_players",
        "source_column": "tournament_id",
        "target_table": "tournaments",
        "target_column": "tournament_id",
        "note": "Tournament result rows are linked to tournaments.",
    },
    {
        "source_table": "handhistories",
        "source_column": "gametype_id",
        "target_table": "gametypes",
        "target_column": "gametype_id",
        "note": "Hands can be linked to blinds and game type metadata.",
    },
]

STAT_MAPPINGS = [
    {
        "metric": "Hands",
        "formula": "SUM(compiledplayerresults.totalhands)",
        "source_table": "compiledplayerresults",
        "confidence": "high",
    },
    {
        "metric": "bb/100",
        "formula": "SUM(totalbbswon) / SUM(totalhands) * 100",
        "source_table": "compiledplayerresults",
        "confidence": "high",
    },
    {
        "metric": "VPIP",
        "formula": "SUM(vpiphands) / SUM(couldvpip) * 100",
        "source_table": "compiledplayerresults",
        "confidence": "high",
    },
    {
        "metric": "PFR",
        "formula": "SUM(pfrhands) / SUM(couldpfr) * 100",
        "source_table": "compiledplayerresults",
        "confidence": "high",
    },
    {
        "metric": "3Bet",
        "formula": "SUM(didthreebet) / SUM(couldthreebet) * 100",
        "source_table": "compiledplayerresults",
        "confidence": "high",
    },
    {
        "metric": "Squeeze",
        "formula": "SUM(didsqueeze) / SUM(couldsqueeze) * 100",
        "source_table": "compiledplayerresults",
        "confidence": "high",
    },
    {
        "metric": "WTSD",
        "formula": "SUM(sawshowdown) / SUM(sawflop) * 100",
        "source_table": "compiledplayerresults",
        "confidence": "high",
    },
    {
        "metric": "W$SD",
        "formula": "SUM(wonshowdown) / SUM(sawshowdown) * 100",
        "source_table": "compiledplayerresults",
        "confidence": "high",
    },
    {
        "metric": "WWSF",
        "formula": "SUM(wonhandwhensawflop) / SUM(sawflop) * 100",
        "source_table": "compiledplayerresults",
        "confidence": "high",
    },
    {
        "metric": "Agg",
        "formula": "SUM(totalbets) / SUM(totalcalls)",
        "source_table": "compiledplayerresults",
        "confidence": "medium",
    },
    {
        "metric": "Fold to 3Bet",
        "formula": "SUM(foldedtothreebetpreflop) / SUM(facedthreebetpreflop) * 100",
        "source_table": "compiledplayerresults",
        "confidence": "high",
    },
    {
        "metric": "Flop CBet",
        "formula": "SUM(flopcontinuationbetmade) / SUM(flopcontinuationbetpossible) * 100",
        "source_table": "compiledplayerresults",
        "confidence": "high",
    },
]


def build_schema_overview(settings: Settings) -> dict[str, Any]:
    database_path = settings.hm3_db_path
    if database_path is None:
        warning = missing_database_path_warning()
        return {
            "configured": False,
            "connected": False,
            "warnings": [warning],
            "tables": [],
            "relationships": KNOWN_RELATIONSHIPS,
            "stat_mappings": STAT_MAPPINGS,
        }

    database_name = Path(database_path).name
    try:
        with connect_readonly(database_path) as connection:
            tables = list_database_tables(connection)
            return {
                "configured": True,
                "connected": True,
                "database_name": database_name,
                "tables": tables,
                "relationships": KNOWN_RELATIONSHIPS,
                "stat_mappings": STAT_MAPPINGS,
                "warnings": schema_warnings(tables),
            }
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return {
            "configured": True,
            "connected": False,
            "database_name": database_name,
            "tables": [],
            "relationships": KNOWN_RELATIONSHIPS,
            "stat_mappings": STAT_MAPPINGS,
            "warnings": warnings,
            "error": error,
        }


def list_database_tables(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    tables = []
    for row in rows:
        table_name = str(row["name"])
        columns = [
            {
                "name": column["name"],
                "type": column["type"],
                "not_null": bool(column["notnull"]),
                "primary_key": bool(column["pk"]),
            }
            for column in connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        ]
        count = connection.execute(f'SELECT COUNT(*) AS row_count FROM "{table_name}"').fetchone()[
            "row_count"
        ]
        tables.append(
            {
                "name": table_name,
                "row_count": int(count),
                "columns": columns,
                "role": table_role(table_name),
                "contains_sensitive_text": table_name in {"handhistories", "error_hands"},
            }
        )
    return tables


def table_role(table_name: str) -> str:
    roles = {
        "compiledplayerresults": "HM3 aggregate player stats",
        "players": "Player identity and aliases",
        "handhistories": "Historical hand text and metadata",
        "tournaments": "Tournament metadata",
        "tournament_players": "Tournament results by player",
        "gametypes": "Blinds, ante, table size, game type",
        "imported_files": "Import metadata",
        "import_summaries": "Import run summaries",
        "error_hands": "Import errors and failed hand text",
    }
    return roles.get(table_name, "HM3 support table")


def schema_warnings(tables: list[dict[str, Any]]) -> list[str]:
    names = {table["name"] for table in tables}
    warnings = []
    if "compiledplayerresults" not in names:
        warnings.append("compiledplayerresults is missing, aggregate HM3 stats are unavailable.")
    if "handhistories" in names:
        warnings.append("handhistories contains raw hand text and is not copied to snapshots.")
    if "error_hands" in names:
        warnings.append(
            "error_hands may contain raw failed hand text and is not copied to snapshots."
        )
    return warnings


def create_explorer_snapshot(settings: Settings) -> dict[str, Any]:
    overview = build_schema_overview(settings)
    if not overview.get("connected"):
        return {
            "created": False,
            "database_name": overview.get("database_name"),
            "warnings": overview.get("warnings", []),
            "error": overview.get("error") or "Database is not connected.",
        }

    export_dir = Path("local_exports")
    export_dir.mkdir(exist_ok=True)
    database_name = overview.get("database_name") or "hm3"
    snapshot_name = f"{Path(database_name).stem}_schema_snapshot.sqlite"
    snapshot_path = export_dir / snapshot_name
    if snapshot_path.exists():
        snapshot_path.unlink()

    connection = sqlite3.connect(snapshot_path)
    try:
        write_snapshot(connection, settings, overview)
    finally:
        connection.close()

    return {
        "created": True,
        "database_name": database_name,
        "snapshot_name": snapshot_name,
        "relative_path": str(snapshot_path),
        "tables": SAFE_SNAPSHOT_TABLES,
        "warnings": [
            "Snapshot is sanitized and does not include full hand text or full source path."
        ],
    }


def write_snapshot(
    connection: sqlite3.Connection,
    settings: Settings,
    overview: dict[str, Any],
) -> None:
    connection.executescript(
        """
        CREATE TABLE hm3_tables (
            table_name TEXT PRIMARY KEY,
            row_count INTEGER,
            role TEXT,
            contains_sensitive_text INTEGER
        );
        CREATE TABLE hm3_columns (
            table_name TEXT,
            column_name TEXT,
            column_type TEXT,
            not_null INTEGER,
            primary_key INTEGER
        );
        CREATE TABLE hm3_relationships (
            source_table TEXT,
            source_column TEXT,
            target_table TEXT,
            target_column TEXT,
            note TEXT
        );
        CREATE TABLE hm3_stat_mappings (
            metric TEXT,
            formula TEXT,
            source_table TEXT,
            confidence TEXT
        );
        CREATE TABLE hm3_table_counts (
            table_name TEXT PRIMARY KEY,
            row_count INTEGER
        );
        CREATE TABLE hm3_metric_preview (
            metric TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE agent_tool_catalog (
            tool_name TEXT PRIMARY KEY,
            description TEXT
        );
        """
    )
    for table in overview["tables"]:
        connection.execute(
            "INSERT INTO hm3_tables VALUES (?, ?, ?, ?)",
            (
                table["name"],
                table["row_count"],
                table["role"],
                int(table["contains_sensitive_text"]),
            ),
        )
        connection.execute(
            "INSERT INTO hm3_table_counts VALUES (?, ?)",
            (table["name"], table["row_count"]),
        )
        for column in table["columns"]:
            connection.execute(
                "INSERT INTO hm3_columns VALUES (?, ?, ?, ?, ?)",
                (
                    table["name"],
                    column["name"],
                    column["type"],
                    int(column["not_null"]),
                    int(column["primary_key"]),
                ),
            )
    for relationship in KNOWN_RELATIONSHIPS:
        connection.execute(
            "INSERT INTO hm3_relationships VALUES (?, ?, ?, ?, ?)",
            tuple(relationship.values()),
        )
    for mapping in STAT_MAPPINGS:
        connection.execute(
            "INSERT INTO hm3_stat_mappings VALUES (?, ?, ?, ?)",
            tuple(mapping.values()),
        )
    stats = build_hm3_player_stats(settings).get("stats", {})
    for metric, value in stats.items():
        connection.execute(
            "INSERT INTO hm3_metric_preview VALUES (?, ?)",
            (metric, str(value)),
        )
    for tool in tool_definitions_for_snapshot():
        connection.execute(
            "INSERT INTO agent_tool_catalog VALUES (?, ?)",
            (tool["name"], tool.get("description", "")),
        )
    connection.commit()


def tool_definitions_for_snapshot() -> list[dict[str, Any]]:
    from poker_ai_coach.agent.tool_registry import tool_definitions

    return tool_definitions()
