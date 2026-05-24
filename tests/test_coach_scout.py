import sqlite3
from pathlib import Path

from poker_ai_coach.config import Settings
from poker_ai_coach.reports.coach_scout import build_coach_scout_report


def create_scout_db(database_path: Path) -> None:
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
    rows = [
        (
            1,
            "T-1",
            "2026-05-20 10:00:00",
            "\n".join(
                [
                    "Poker Hand #1: Tournament #T-1 - Level5(100/200)",
                    "Table '1' 6-max Seat #3 is the button",
                    "Seat 1: Villain1 (5000 in chips)",
                    "Seat 2: Hero (4000 in chips)",
                    "Seat 3: Villain2 (8000 in chips)",
                    "Dealt to Hero [Ah Kh]",
                    "Hero: raises 400 to 600",
                    "Villain1: raises 3400 to 4000 and is all-in",
                    "Hero: calls 3400 and is all-in",
                    "Total pot 8200 | Rake 0",
                ]
            ),
        ),
        (
            2,
            "T-1",
            "2026-05-20 10:05:00",
            "\n".join(
                [
                    "Poker Hand #2: Tournament #T-1 - Level5(100/200)",
                    "Table '1' 6-max Seat #4 is the button",
                    "Seat 2: Hero (7000 in chips)",
                    "Seat 4: Villain2 (8000 in chips)",
                    "Dealt to Hero [Qs Qd]",
                    "Hero: raises 500 to 700",
                    "Hero: bets 2400",
                    "Total pot 5600 | Rake 0",
                ]
            ),
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
    connection.commit()
    connection.close()


def test_coach_scout_finds_action_patterns_and_hand_ids(tmp_path):
    database_path = tmp_path / "scout.hmdb"
    create_scout_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    report = build_coach_scout_report(settings)

    assert report["connected"] is True
    assert report["report_type"] == "coach_scout"
    assert report["hero_text_hands"] == 2
    assert report["hero_all_in_hands"] == 1
    assert report["hero_large_pot_hands"] == 2
    assert report["hero_action_counts"]["all-in call"] == 1
    assert report["hero_action_counts"]["raise"] == 2
    assert report["top_review_hands"][0]["hand_id"] == 1
    assert any(insight["hand_ids"] for insight in report["insights"])


def test_coach_scout_handles_missing_database_path():
    settings = Settings(HM3_DB_PATH=None, HERO_NAME="surok_valera")

    report = build_coach_scout_report(settings)

    assert report["connected"] is False
    assert report["insights"] == []
    assert report["warnings"]
