import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from poker_ai_coach.config import Settings
from poker_ai_coach.main import app
from poker_ai_coach.reports.study_plan import build_study_plan


def create_study_db(database_path: Path) -> None:
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
            "200",
            "2026-05-20 10:00:00",
            "Hand #1\nsurok_valera opens and wins small pot.",
        ),
        (
            2,
            "200",
            "1970-01-01 00:00:00",
            "Hand #2\nsurok_valera calls all-in. Total pot 9000",
        ),
        (
            3,
            "201",
            "2026-05-21 11:00:00",
            "Hand #3\nVillain all in. surok_valera folds. Total pot 7000",
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
    connection.execute("INSERT INTO error_hands (handhistory_id) VALUES (2)")
    connection.execute("INSERT INTO tournaments (tournament_id) VALUES (20)")
    connection.execute("INSERT INTO tournaments (tournament_id) VALUES (21)")
    connection.execute("INSERT INTO tournament_players (tournament_id, player_id) VALUES (20, 1)")
    connection.commit()
    connection.close()


def test_study_plan_builds_focus_hands_drills_and_checklist(tmp_path):
    database_path = tmp_path / "study.hmdb"
    create_study_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    plan = build_study_plan(settings)

    assert plan.connected is True
    assert 1 <= len(plan.focus_areas) <= 3
    assert plan.hands_to_review
    assert len(plan.hands_to_review) <= 10
    assert plan.drills
    assert plan.weekly_checklist
    assert plan.confidence in {"high", "medium", "low"}
    assert {hand.hand_id for hand in plan.hands_to_review}.issuperset({2, 3})
    assert plan.focus_areas[0].title in {
        "Review category: all-in",
        "Review category: large pot",
        "All-in review volume",
    }


def test_study_plan_endpoint(monkeypatch, tmp_path):
    database_path = tmp_path / "study.hmdb"
    create_study_db(database_path)
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    monkeypatch.setenv("HERO_NAME", "surok_valera")
    client = TestClient(app)

    response = client.get("/api/study-plan")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["focus_areas"]
    assert data["hands_to_review"]


def test_study_plan_coach_endpoint_is_safe_when_ai_disabled(monkeypatch, tmp_path):
    database_path = tmp_path / "study.hmdb"
    create_study_db(database_path)
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post("/api/coach/study-plan")

    assert response.status_code == 200
    data = response.json()
    assert data["ai_configured"] is False
    assert "No data was sent to an AI provider." in data["content"]
