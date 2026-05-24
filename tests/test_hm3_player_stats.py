from pathlib import Path

from poker_ai_coach.config import Settings
from poker_ai_coach.reports.hm3_player_stats import build_hm3_player_stats


def create_stats_db(database_path: Path) -> None:
    import sqlite3

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
    connection.execute("INSERT INTO players VALUES (1, 'Hero', 1, 1000)")
    connection.execute(
        """
        INSERT INTO compiledplayerresults VALUES (
            1, 1, 202601, 6, 1, 1,
            1000, 5000, 1000, 120.0,
            240, 180, 1000, 1000,
            100, 9, 50, 5,
            420, 170, 90, 210,
            300, 100, 800, 240,
            80, 36, 20, 8,
            300, 180, 200, 100
        )
        """
    )
    connection.commit()
    connection.close()


def test_hm3_player_stats_uses_compiled_results(tmp_path: Path):
    database_path = tmp_path / "stats.hmdb"
    create_stats_db(database_path)

    report = build_hm3_player_stats(Settings(HM3_DB_PATH=database_path, HERO_NAME="surok_valera"))

    assert report["connected"] is True
    assert report["hero_player_name"] == "Hero"
    assert report["stats"]["total_hands"] == 1000
    assert report["stats"]["bb100"] == 12.0
    assert report["stats"]["vpip_pct"] == 24.0
    assert report["stats"]["pfr_pct"] == 18.0
    assert report["stats"]["three_bet_pct"] == 9.0
    assert report["stats"]["wtsd_pct"] == 40.48
    assert report["monthly_trend"][0]["period"] == 202601
