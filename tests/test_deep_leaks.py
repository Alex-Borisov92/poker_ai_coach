import sqlite3
from pathlib import Path

from poker_ai_coach.config import Settings
from poker_ai_coach.reports.deep_leaks import (
    analyze_hand_actions_batch,
    find_stat_leaks,
    get_candidate_hands_for_leak,
    get_hand_details_batch,
    get_monthly_hm3_stats,
)


def create_deep_db(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE players (
            player_id INTEGER PRIMARY KEY,
            playername TEXT,
            pokersite_id INTEGER,
            tourneyhands INTEGER
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE compiledplayerresults (
            compiledplayerresults_id INTEGER PRIMARY KEY,
            player_id INTEGER,
            playedyearandmonth INTEGER,
            numberofplayers INTEGER,
            gametype_id INTEGER,
            bbgroup_id INTEGER,
            totalhands INTEGER,
            totalamountwonincents INTEGER,
            totalrakeincents INTEGER,
            totalbbswon REAL,
            vpiphands INTEGER,
            pfrhands INTEGER,
            couldvpip INTEGER,
            couldpfr INTEGER,
            couldthreebet INTEGER,
            didthreebet INTEGER,
            couldsqueeze INTEGER,
            didsqueeze INTEGER,
            sawflop INTEGER,
            sawshowdown INTEGER,
            wonshowdown INTEGER,
            wonhandwhensawflop INTEGER,
            totalbets INTEGER,
            totalcalls INTEGER,
            totalpostflopstreetsseen INTEGER,
            totalaggressivepostflopstreetsseen INTEGER,
            facedthreebetpreflop INTEGER,
            foldedtothreebetpreflop INTEGER,
            facedfourbetpreflop INTEGER,
            foldedtofourbetpreflop INTEGER,
            flopcontinuationbetpossible INTEGER,
            flopcontinuationbetmade INTEGER,
            facingflopcontinuationbet INTEGER,
            foldedtoflopcontinuationbet INTEGER
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE handhistories (
            handhistory_id INTEGER PRIMARY KEY,
            handhistory TEXT,
            handtimestamp TEXT,
            tournament_number TEXT
        )
        """
    )
    connection.execute("INSERT INTO players VALUES (1, 'hero', 1, 1000)")
    connection.execute(
        """
        INSERT INTO compiledplayerresults VALUES (
            1, 1, 202605, 6, 1, 1,
            10000, 5000, 1000, 900.0,
            2700, 1900, 10000, 10000,
            1000, 85, 500, 40,
            4000, 1600, 780, 1700,
            2600, 1900, 8000, 1800,
            800, 380, 120, 40,
            3000, 1500, 2400, 950
        )
        """
    )
    for hand_id in range(1, 13):
        connection.execute(
            """
            INSERT INTO handhistories VALUES (?, ?, ?, ?)
            """,
            (
                hand_id,
                "\n".join(
                    [
                        "PokerStars Hand",
                        "Seat 1: hero (2500)",
                        "Level 1 (50/100)",
                        "Dealt to hero [As Ks]",
                        "hero: calls 200",
                        "villain: raises to 600",
                        "hero: calls 400",
                        "*** FLOP *** [Ah 7d 2c]",
                        "hero: bets 1200",
                        "villain: raises all-in",
                        "hero: calls all-in",
                        "Total pot 12000",
                    ]
                ),
                "2026-05-20 12:00:00",
                "777",
            ),
        )
    connection.commit()
    connection.close()


def test_monthly_stats_and_leaks_use_aggregate_counters(tmp_path: Path):
    database_path = tmp_path / "deep.hmdb"
    create_deep_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera")

    monthly = get_monthly_hm3_stats(settings, period="2026-05")
    leak_result = find_stat_leaks(settings, period="2026-05", limit=10)

    assert monthly["connected"] is True
    assert monthly["period"] == "202605"
    assert monthly["stats"]["vpip_pfr_gap_pct"] == 8.0
    assert len(leak_result["leaks"]) >= 3
    assert leak_result["leaks"][0]["severity"] in {"critical", "high"}
    assert leak_result["leaks"][0]["related_hand_ids"]


def test_deep_hand_tools_are_bounded(tmp_path: Path):
    database_path = tmp_path / "deep.hmdb"
    create_deep_db(database_path)
    settings = Settings(HM3_DB_PATH=database_path, HERO_NAME="hero")

    candidates = get_candidate_hands_for_leak(settings, "large_pot_quality", "202605", limit=5)
    details = get_hand_details_batch(settings, list(range(1, 13)), limit=20)
    analyses = analyze_hand_actions_batch(settings, list(range(1, 13)), limit=20)

    assert len(candidates["hands"]) == 5
    assert len(details["hands"]) == 10
    assert len(analyses["hands"]) == 10
    assert analyses["hands"][0]["hero_actions"]
