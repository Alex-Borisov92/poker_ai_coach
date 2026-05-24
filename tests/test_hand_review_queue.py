import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from poker_ai_coach.config import Settings
from poker_ai_coach.main import app
from poker_ai_coach.reports.hand_review_queue import build_review_queue, get_hand_detail


def create_hands_db(database_path: Path) -> None:
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
    connection.execute(
        """
        CREATE TABLE error_hands (
            error_hand_id INTEGER PRIMARY KEY,
            handhistory_id INTEGER
        )
        """
    )
    rows = [
        (
            1,
            "T-1",
            "2026-05-20 10:00:00",
            "Poker hand #1\nHero surok_valera raises.\nTotal pot 1200",
        ),
        (
            2,
            "T-1",
            "2026-05-21 11:00:00",
            "Poker hand #2\nVillain goes all-in. surok_valera calls.\nTotal pot 9000",
        ),
        (
            3,
            "T-2",
            "1970-01-01 00:00:00",
            "Poker hand #3\nsurok_valera folds preflop.",
        ),
        (
            4,
            "T-3",
            "2026-05-22 12:00:00",
            "Poker hand #4\nNo nickname here.\nTotal pot 300",
        ),
    ]
    connection.executemany(
        """
        INSERT INTO handhistories
            (handhistory_id, tournament_number, handtimestamp, handhistory)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )
    connection.execute("INSERT INTO error_hands (handhistory_id) VALUES (3)")
    connection.commit()
    connection.close()


def test_review_queue_selects_interesting_hands_with_deterministic_order(tmp_path):
    database_path = tmp_path / "hands.hmdb"
    create_hands_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    queue = build_review_queue(settings, limit=10)

    assert queue.connected is True
    assert [hand.hand_id for hand in queue.hands] == [3, 2, 1, 4]
    assert queue.hands[0].source == "error_hands"
    assert "HM3 import error" in queue.hands[0].reasons
    assert queue.hands[0].hand_date is None
    assert queue.hands[0].is_date_unknown is True
    assert "all-in" in queue.hands[1].reasons
    assert "large pot" in queue.hands[1].reasons


def test_review_queue_respects_limit(tmp_path):
    database_path = tmp_path / "hands.hmdb"
    create_hands_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    queue = build_review_queue(settings, limit=2)

    assert [hand.hand_id for hand in queue.hands] == [3, 2]


def test_review_queue_uses_hero_text_fallback_alias(tmp_path):
    database_path = tmp_path / "hands.hmdb"
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
    connection.execute(
        """
        CREATE TABLE error_hands (
            error_hand_id INTEGER PRIMARY KEY,
            handhistory_id INTEGER
        )
        """
    )
    connection.execute(
        """
        INSERT INTO handhistories
            (handhistory_id, tournament_number, handtimestamp, handhistory)
        VALUES (1, 'T-1', '2026-05-20 10:00:00', 'Hero raises and wins.')
        """
    )
    connection.commit()
    connection.close()
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    queue = build_review_queue(settings, limit=10)

    assert [hand.hand_id for hand in queue.hands] == [1]
    assert "hero name" in queue.hands[0].reasons


def test_hand_detail_returns_hand_text(tmp_path):
    database_path = tmp_path / "hands.hmdb"
    create_hands_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    detail = get_hand_detail(settings, hand_id=2)

    assert detail.connected is True
    assert detail.hand_id == 2
    assert detail.tournament_number == "T-1"
    assert detail.hand_date == "2026-05-21"
    assert "Villain goes all-in" in detail.hand_text
    assert detail.source == "handhistories"


def test_review_queue_endpoint(monkeypatch, tmp_path):
    database_path = tmp_path / "hands.hmdb"
    create_hands_db(database_path)
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    monkeypatch.setenv("HERO_NAME", "surok_valera")
    client = TestClient(app)

    response = client.get("/api/hands/review-queue?limit=2")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert [hand["hand_id"] for hand in data["hands"]] == [3, 2]


def test_hand_detail_endpoint(monkeypatch, tmp_path):
    database_path = tmp_path / "hands.hmdb"
    create_hands_db(database_path)
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    client = TestClient(app)

    response = client.get("/api/hands/2")

    assert response.status_code == 200
    data = response.json()
    assert data["hand_id"] == 2
    assert "Villain goes all-in" in data["hand_text"]
