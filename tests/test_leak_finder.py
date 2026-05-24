import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from poker_ai_coach.config import Settings
from poker_ai_coach.main import app
from poker_ai_coach.reports.leak_finder import build_leak_finder_report


def create_leak_db(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE handhistories (
            handhistory_id INTEGER PRIMARY KEY,
            tournament_number TEXT,
            handtimestamp TEXT,
            handhistory TEXT
        )
        """
    )
    connection.execute("CREATE TABLE error_hands (error_hand_id INTEGER PRIMARY KEY)")
    connection.execute("CREATE TABLE tournaments (tournament_id INTEGER PRIMARY KEY)")
    connection.execute(
        """
        CREATE TABLE tournament_players (
            tournament_player_id INTEGER PRIMARY KEY,
            tournament_id INTEGER,
            player_id INTEGER
        )
        """
    )
    hands = [
        (
            1,
            "100",
            "2026-05-20 10:00:00",
            "Hand #1\nsurok_valera raises.\nTotal pot 1200",
        ),
        (
            2,
            "100",
            "1970-01-01 00:00:00",
            "Hand #2\nsurok_valera calls all-in.\nTotal pot 9000",
        ),
        (
            3,
            "101",
            "2026-05-21 11:00:00",
            "Hand #3\nVillain all in. No nickname here.\nTotal pot 7000",
        ),
        (
            4,
            "101",
            "2026-05-21 12:00:00",
            "Hand #4\nsurok_valera folds.",
        ),
    ]
    connection.executemany(
        """
        INSERT INTO handhistories
            (handhistory_id, tournament_number, handtimestamp, handhistory)
        VALUES (?, ?, ?, ?)
        """,
        hands,
    )
    connection.execute("INSERT INTO error_hands DEFAULT VALUES")
    connection.execute("INSERT INTO error_hands DEFAULT VALUES")
    connection.execute("INSERT INTO tournaments (tournament_id) VALUES (10)")
    connection.execute("INSERT INTO tournaments (tournament_id) VALUES (11)")
    connection.execute("INSERT INTO tournament_players (tournament_id, player_id) VALUES (10, 1)")
    connection.commit()
    connection.close()


def test_leak_finder_reports_supported_metrics(tmp_path):
    database_path = tmp_path / "leaks.hmdb"
    create_leak_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    report = build_leak_finder_report(settings)

    leak_keys = {leak.leak_key for leak in report.leaks}
    assert report.connected is True
    assert report.total_hands == 4
    assert "invalid_date_coverage" in leak_keys
    assert "hm3_import_errors" in leak_keys
    assert "all_in_review_volume" in leak_keys
    assert "hero_text_partial" in leak_keys
    assert "tournament_result_coverage" in leak_keys
    assert any(leak.confidence in {"high", "medium", "low"} for leak in report.leaks)
    all_in_leak = next(leak for leak in report.leaks if leak.leak_key == "all_in_review_volume")
    assert all_in_leak.related_hand_ids == [2, 3]


def test_leak_finder_missing_tables_are_reported(tmp_path):
    database_path = tmp_path / "missing.hmdb"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE handhistories (
            handhistory_id INTEGER PRIMARY KEY,
            tournament_number TEXT,
            handtimestamp TEXT,
            handhistory TEXT
        )
        """
    )
    connection.commit()
    connection.close()
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    report = build_leak_finder_report(settings)

    assert "error_hands table is missing." in report.missing_data
    assert "tournaments table is missing." in report.missing_data


def test_leak_finder_endpoint(monkeypatch, tmp_path):
    database_path = tmp_path / "leaks.hmdb"
    create_leak_db(database_path)
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    monkeypatch.setenv("HERO_NAME", "surok_valera")
    client = TestClient(app)

    response = client.get("/api/reports/leak-finder")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["total_hands"] == 4
    assert data["leaks"]


def test_leak_finder_reports_tournament_result_pressure(tmp_path):
    database_path = tmp_path / "result_pressure.hmdb"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE handhistories (
            handhistory_id INTEGER PRIMARY KEY,
            tournament_number TEXT,
            handtimestamp TEXT,
            handhistory TEXT
        )
        """
    )
    connection.execute("CREATE TABLE error_hands (error_hand_id INTEGER PRIMARY KEY)")
    connection.execute(
        """
        CREATE TABLE players (
            player_id INTEGER PRIMARY KEY,
            playername TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE tournaments (
            tournament_id INTEGER PRIMARY KEY,
            buyin_in_cents INTEGER,
            rake_in_cents INTEGER,
            bounty_in_cents INTEGER
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE tournament_players (
            tournament_player_id INTEGER PRIMARY KEY,
            tournament_id INTEGER,
            player_id INTEGER,
            finish_position INTEGER,
            winnings_in_cents INTEGER,
            total_bounty_in_cents INTEGER
        )
        """
    )
    connection.execute("INSERT INTO players (player_id, playername) VALUES (1, 'surok_valera')")
    for tournament_id in range(1, 26):
        connection.execute(
            """
            INSERT INTO tournaments
              (tournament_id, buyin_in_cents, rake_in_cents, bounty_in_cents)
            VALUES (?, 100, 10, 0)
            """,
            (tournament_id,),
        )
        connection.execute(
            """
            INSERT INTO tournament_players
              (tournament_id, player_id, finish_position, winnings_in_cents, total_bounty_in_cents)
            VALUES (?, 1, 10, 0, 0)
            """,
            (tournament_id,),
        )
    connection.commit()
    connection.close()
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    report = build_leak_finder_report(settings)

    pressure = next(leak for leak in report.leaks if leak.leak_key == "tournament_result_pressure")
    assert "25 linked tournaments" in pressure.evidence
    assert pressure.confidence == "low"


def test_leak_finder_uses_hero_fallback_alias(tmp_path):
    database_path = tmp_path / "fallback.hmdb"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE handhistories (
            handhistory_id INTEGER PRIMARY KEY,
            tournament_number TEXT,
            handtimestamp TEXT,
            handhistory TEXT
        )
        """
    )
    connection.execute("CREATE TABLE error_hands (error_hand_id INTEGER PRIMARY KEY)")
    connection.execute(
        """
        CREATE TABLE players (
            player_id INTEGER PRIMARY KEY,
            playername TEXT
        )
        """
    )
    connection.execute("CREATE TABLE tournaments (tournament_id INTEGER PRIMARY KEY)")
    connection.execute(
        """
        CREATE TABLE tournament_players (
            tournament_player_id INTEGER PRIMARY KEY,
            tournament_id INTEGER,
            player_id INTEGER
        )
        """
    )
    connection.execute("INSERT INTO players (player_id, playername) VALUES (1, 'hero')")
    connection.execute(
        """
        INSERT INTO handhistories
            (handhistory_id, tournament_number, handtimestamp, handhistory)
        VALUES (1, 'T-1', '2026-05-20 10:00:00', 'Hero calls all-in. Total pot 9000')
        """
    )
    connection.commit()
    connection.close()
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    report = build_leak_finder_report(settings)

    assert not any("Hero missing from hand text" == leak.leak_name for leak in report.leaks)
    assert not any("Hero was not found in players" in note for note in report.missing_data)


def test_analyze_leaks_endpoint_is_safe_when_ai_disabled(monkeypatch, tmp_path):
    database_path = tmp_path / "leaks.hmdb"
    create_leak_db(database_path)
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post("/api/coach/analyze-leaks")

    assert response.status_code == 200
    data = response.json()
    assert data["ai_configured"] is False
    assert "No data was sent to an AI provider." in data["content"]
