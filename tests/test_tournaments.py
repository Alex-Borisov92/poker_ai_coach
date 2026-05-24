import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from poker_ai_coach.config import Settings
from poker_ai_coach.main import app
from poker_ai_coach.repositories.hm3_repository import get_tournament_hands, get_tournaments


def create_tournaments_db(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE tournaments (
            tournament_id INTEGER PRIMARY KEY,
            tournament_number TEXT,
            first_hand_timestamp TEXT,
            last_hand_timestamp TEXT,
            number_of_entrants INTEGER,
            buyin_in_cents INTEGER,
            rake_in_cents INTEGER,
            bounty_in_cents INTEGER
        )
        """
    )
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
    connection.execute(
        """
        CREATE TABLE error_hands (
            error_hand_id INTEGER PRIMARY KEY,
            handhistory_id INTEGER
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO tournaments (
            tournament_number,
            first_hand_timestamp,
            last_hand_timestamp,
            number_of_entrants,
            buyin_in_cents,
            rake_in_cents,
            bounty_in_cents
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("T-100", "2026-05-20 10:00:00", "2026-05-20 11:30:00", 125, 110, 10, 0),
            ("T-200", "1970-01-01 00:00:00", "1970-01-01 00:00:00", None, 220, 20, 50),
            ("T-300", "2026-05-22 12:00:00", "2026-05-22 13:00:00", 80, 0, 0, 0),
        ],
    )
    connection.executemany(
        """
        INSERT INTO handhistories
            (handhistory_id, tournament_number, handtimestamp, handhistory)
        VALUES (?, ?, ?, ?)
        """,
        [
            (1, "T-100", "2026-05-20 10:00:00", "surok_valera raises. Total pot 400"),
            (2, "T-100", "2026-05-20 10:10:00", "Villain all-in. surok_valera calls."),
            (3, "T-200", "1970-01-01 00:00:00", "surok_valera folds."),
            (4, "T-300", "2026-05-22 12:15:00", "No special action."),
        ],
    )
    connection.execute("INSERT INTO error_hands (handhistory_id) VALUES (2)")
    connection.commit()
    connection.close()


def test_tournaments_include_counts_and_valid_dates(tmp_path):
    database_path = tmp_path / "tournaments.hmdb"
    create_tournaments_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path)

    result = get_tournaments(settings)

    assert result.connected is True
    by_number = {tournament.tournament_number: tournament for tournament in result.tournaments}
    assert by_number["T-100"].hand_count == 2
    assert by_number["T-100"].error_count == 1
    assert by_number["T-100"].first_hand_date == "2026-05-20"
    assert by_number["T-100"].last_hand_date == "2026-05-20"
    assert by_number["T-100"].buyin_in_cents == 110
    assert by_number["T-100"].rake_in_cents == 10
    assert by_number["T-100"].entrants == 125
    assert by_number["T-200"].first_hand_date is None
    assert by_number["T-200"].is_date_unknown is True


def test_tournaments_filters_search_date_and_errors(tmp_path):
    database_path = tmp_path / "tournaments.hmdb"
    create_tournaments_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path)

    searched = get_tournaments(settings, search="200")
    dated = get_tournaments(settings, date_from="2026-05-21", date_to="2026-05-23")
    with_errors = get_tournaments(settings, only_with_errors=True)

    assert [tournament.tournament_number for tournament in searched.tournaments] == ["T-200"]
    assert [tournament.tournament_number for tournament in dated.tournaments] == ["T-300"]
    assert [tournament.tournament_number for tournament in with_errors.tournaments] == ["T-100"]
    assert "Tournaments with unknown dates are hidden by date filters." in dated.warnings


def test_tournament_hands_returns_related_hands(tmp_path):
    database_path = tmp_path / "tournaments.hmdb"
    create_tournaments_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path)

    result = get_tournament_hands(settings, tournament_number="T-100")

    assert result.connected is True
    assert [hand.hand_id for hand in result.hands] == [2, 1]
    assert result.hands[0].source == "error_hands"
    assert "all-in" in result.hands[0].reasons


def test_tournaments_endpoint(monkeypatch, tmp_path):
    database_path = tmp_path / "tournaments.hmdb"
    create_tournaments_db(database_path)
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    client = TestClient(app)

    response = client.get("/api/tournaments?only_with_errors=true")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert [tournament["tournament_number"] for tournament in data["tournaments"]] == ["T-100"]


def test_tournament_hands_endpoint(monkeypatch, tmp_path):
    database_path = tmp_path / "tournaments.hmdb"
    create_tournaments_db(database_path)
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    client = TestClient(app)

    response = client.get("/api/tournaments/T-100/hands")

    assert response.status_code == 200
    data = response.json()
    assert data["tournament_number"] == "T-100"
    assert [hand["hand_id"] for hand in data["hands"]] == [2, 1]
