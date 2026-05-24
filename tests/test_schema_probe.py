import sqlite3

import pytest
from poker_ai_coach.db.hm3_connection import connect_readonly
from poker_ai_coach.db.schema_probe import EXPECTED_TABLES, probe_schema


def create_fixture_db(database_path):
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY, playername TEXT)")
    connection.execute("CREATE TABLE handhistories (handhistory_id INTEGER PRIMARY KEY)")
    connection.execute("CREATE TABLE tournaments (tournament_id INTEGER PRIMARY KEY)")
    connection.execute("CREATE TABLE imported_files (imported_file_id INTEGER PRIMARY KEY)")
    connection.execute("INSERT INTO players (playername) VALUES ('hero_test')")
    connection.execute("INSERT INTO handhistories DEFAULT VALUES")
    connection.execute("INSERT INTO handhistories DEFAULT VALUES")
    connection.commit()
    connection.close()


def test_probe_schema_returns_tables_counts_and_missing_tables(tmp_path):
    database_path = tmp_path / "tiny.hmdb"
    create_fixture_db(database_path)

    with connect_readonly(database_path) as connection:
        tables, table_counts, missing_tables = probe_schema(connection)

    assert tables == ["handhistories", "imported_files", "players", "tournaments"]
    assert table_counts == {
        "handhistories": 2,
        "tournaments": 0,
        "players": 1,
        "imported_files": 0,
    }
    assert "tournament_players" in missing_tables
    assert set(missing_tables).issubset(set(EXPECTED_TABLES))


def test_readonly_connection_blocks_write_operations(tmp_path):
    database_path = tmp_path / "tiny.hmdb"
    create_fixture_db(database_path)

    with connect_readonly(database_path) as connection:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("INSERT INTO players (playername) VALUES ('bad_write')")

        with pytest.raises(sqlite3.OperationalError):
            connection.execute("CREATE TABLE bad_table (id INTEGER)")
