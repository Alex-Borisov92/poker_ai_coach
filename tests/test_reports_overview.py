import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from poker_ai_coach.config import Settings
from poker_ai_coach.main import app
from poker_ai_coach.reports.overview import build_overview_report


def create_overview_db(database_path: Path, hero_name: str = "surok_valera") -> None:
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY, playername TEXT)")
    connection.execute(
        """
        CREATE TABLE handhistories (
            handhistory_id INTEGER PRIMARY KEY,
            handtimestamp TEXT
        )
        """
    )
    connection.execute("CREATE TABLE tournaments (tournament_id INTEGER PRIMARY KEY)")
    connection.execute("CREATE TABLE imported_files (imported_file_id INTEGER PRIMARY KEY)")
    connection.execute("CREATE TABLE error_hands (error_hand_id INTEGER PRIMARY KEY)")
    connection.execute("INSERT INTO players (playername) VALUES (?)", (hero_name,))
    connection.execute("INSERT INTO handhistories (handtimestamp) VALUES ('2026-05-20 12:00:00')")
    connection.execute("INSERT INTO handhistories (handtimestamp) VALUES ('2026-05-22 13:00:00')")
    connection.execute("INSERT INTO handhistories (handtimestamp) VALUES ('1970-01-01 00:00:00')")
    connection.execute("INSERT INTO tournaments DEFAULT VALUES")
    connection.execute("INSERT INTO imported_files DEFAULT VALUES")
    connection.execute("INSERT INTO imported_files DEFAULT VALUES")
    connection.execute("INSERT INTO error_hands DEFAULT VALUES")
    connection.commit()
    connection.close()


def test_overview_report_counts_and_excludes_1970_dates(tmp_path):
    database_path = tmp_path / "overview.hmdb"
    create_overview_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    report = build_overview_report(settings)

    assert report.configured is True
    assert report.connected is True
    assert report.database_name == "overview.hmdb"
    assert report.hero_found is True
    assert report.total_hands == 3
    assert report.tournaments == 1
    assert report.imported_files == 2
    assert report.error_hands == 1
    assert report.valid_date_range.start == "2026-05-20"
    assert report.valid_date_range.end == "2026-05-22"
    assert report.valid_date_count == 2
    assert report.invalid_1970_date_count == 1
    assert "Some hand dates are 1970-01-01 and were treated as unknown." in report.warnings


def test_overview_report_warns_when_hero_is_missing(tmp_path):
    database_path = tmp_path / "overview.hmdb"
    create_overview_db(database_path, hero_name="other_player")
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    report = build_overview_report(settings)

    assert report.hero_found is False
    assert (
        "Hero 'surok_valera' was not found in players. Fallback alias 'hero' was also missing."
    ) in report.warnings


def test_overview_report_uses_hero_fallback_alias(tmp_path):
    database_path = tmp_path / "overview.hmdb"
    create_overview_db(database_path, hero_name="hero")
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    report = build_overview_report(settings)

    assert report.hero_found is True
    assert not any("was not found in players" in warning for warning in report.warnings)


def test_overview_report_warns_about_empty_db(tmp_path):
    database_path = tmp_path / "empty.hmdb"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY, playername TEXT)")
    connection.execute(
        "CREATE TABLE handhistories (handhistory_id INTEGER PRIMARY KEY, handtimestamp TEXT)"
    )
    connection.execute("CREATE TABLE tournaments (tournament_id INTEGER PRIMARY KEY)")
    connection.execute("CREATE TABLE imported_files (imported_file_id INTEGER PRIMARY KEY)")
    connection.execute("CREATE TABLE error_hands (error_hand_id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    report = build_overview_report(settings)

    assert report.total_hands == 0
    assert "Database looks empty for overview tables." in report.warnings


def test_overview_report_warns_about_many_invalid_dates(tmp_path):
    database_path = tmp_path / "many_invalid_dates.hmdb"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY, playername TEXT)")
    connection.execute(
        "CREATE TABLE handhistories (handhistory_id INTEGER PRIMARY KEY, handtimestamp TEXT)"
    )
    connection.execute("CREATE TABLE tournaments (tournament_id INTEGER PRIMARY KEY)")
    connection.execute("CREATE TABLE imported_files (imported_file_id INTEGER PRIMARY KEY)")
    connection.execute("CREATE TABLE error_hands (error_hand_id INTEGER PRIMARY KEY)")
    connection.execute("INSERT INTO players (playername) VALUES ('surok_valera')")
    connection.execute("INSERT INTO handhistories (handtimestamp) VALUES ('2026-05-20 12:00:00')")
    for _ in range(10):
        connection.execute("INSERT INTO handhistories (handtimestamp) VALUES ('1970-01-01')")
    connection.commit()
    connection.close()
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    report = build_overview_report(settings)

    assert report.invalid_1970_date_count == 10
    assert "Many hand dates are invalid, so date coverage may be incomplete." in report.warnings


def test_overview_endpoint_with_fixture_db(monkeypatch, tmp_path):
    database_path = tmp_path / "overview.hmdb"
    create_overview_db(database_path)
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    monkeypatch.setenv("HERO_NAME", "surok_valera")
    client = TestClient(app)

    response = client.get("/api/reports/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["hero_found"] is True
    assert data["total_hands"] == 3
    assert data["invalid_1970_date_count"] == 1
