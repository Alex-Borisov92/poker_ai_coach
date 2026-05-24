import sqlite3
from pathlib import Path

from poker_ai_coach.config import Settings
from poker_ai_coach.db.schema_overview import build_schema_overview, create_explorer_snapshot


def create_schema_db(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE players (
            player_id INTEGER PRIMARY KEY,
            playername TEXT,
            tourneyhands INTEGER
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE compiledplayerresults (
            compiledplayerresults_id INTEGER PRIMARY KEY,
            player_id INTEGER,
            totalhands INTEGER
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE handhistories (
            handhistory_id INTEGER PRIMARY KEY,
            handtimestamp TEXT,
            handhistory TEXT,
            tournament_number TEXT
        )
        """
    )
    connection.execute("INSERT INTO players VALUES (1, 'Hero', 10)")
    connection.execute("INSERT INTO compiledplayerresults VALUES (1, 1, 10)")
    connection.execute(
        "INSERT INTO handhistories VALUES (1, '2026-05-20 10:00:00', 'SECRET HAND TEXT', 'T-1')"
    )
    connection.commit()
    connection.close()


def test_schema_overview_lists_tables_columns_and_stat_mappings(tmp_path: Path):
    database_path = tmp_path / "schema.hmdb"
    create_schema_db(database_path)

    overview = build_schema_overview(Settings(HM3_DB_PATH=database_path))

    table_names = {table["name"] for table in overview["tables"]}
    compiled = next(
        table for table in overview["tables"] if table["name"] == "compiledplayerresults"
    )

    assert overview["connected"] is True
    assert {"players", "compiledplayerresults", "handhistories"} <= table_names
    assert compiled["role"] == "HM3 aggregate player stats"
    assert any(mapping["metric"] == "VPIP" for mapping in overview["stat_mappings"])
    assert any(column["name"] == "totalhands" for column in compiled["columns"])


def test_explorer_snapshot_is_sanitized(tmp_path: Path, monkeypatch):
    database_path = tmp_path / "schema.hmdb"
    create_schema_db(database_path)
    monkeypatch.chdir(tmp_path)

    result = create_explorer_snapshot(Settings(HM3_DB_PATH=database_path))

    snapshot_path = tmp_path / str(result["relative_path"])
    assert result["created"] is True
    assert snapshot_path.exists()
    assert str(database_path) not in str(result)

    connection = sqlite3.connect(snapshot_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        dump_text = "\n".join(connection.iterdump())
    finally:
        connection.close()

    assert {
        "hm3_tables",
        "hm3_columns",
        "hm3_relationships",
        "hm3_stat_mappings",
        "hm3_table_counts",
        "hm3_metric_preview",
        "agent_tool_catalog",
    } <= tables
    assert "SECRET HAND TEXT" not in dump_text
    assert str(database_path) not in dump_text
