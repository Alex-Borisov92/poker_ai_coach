import sqlite3
from pathlib import Path
from typing import Any

from poker_ai_coach.config import Settings
from poker_ai_coach.db.error_messages import database_open_failure, missing_database_path_warning
from poker_ai_coach.db.hm3_connection import connect_readonly
from poker_ai_coach.db.schema_probe import list_tables
from poker_ai_coach.reports.hand_review_queue import table_columns
from poker_ai_coach.reports.hero_aliases import hero_aliases


def build_hm3_player_stats(settings: Settings) -> dict[str, Any]:
    database_path = settings.hm3_db_path
    if database_path is None:
        warning = missing_database_path_warning()
        return {
            "configured": False,
            "connected": False,
            "hero_name": settings.hero_name,
            "warnings": [warning],
            "missing_data": [warning],
        }

    database_name = Path(database_path).name
    try:
        with connect_readonly(database_path) as connection:
            return build_connected_hm3_player_stats(
                connection=connection,
                database_name=database_name,
                hero_name=settings.hero_name,
            )
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return {
            "configured": True,
            "connected": False,
            "database_name": database_name,
            "hero_name": settings.hero_name,
            "warnings": warnings,
            "missing_data": warnings,
            "error": error,
        }


def build_connected_hm3_player_stats(
    connection: sqlite3.Connection,
    database_name: str,
    hero_name: str,
) -> dict[str, Any]:
    tables = set(list_tables(connection))
    missing_data: list[str] = []
    warnings: list[str] = []
    if "compiledplayerresults" not in tables:
        warning = "compiledplayerresults table is missing. HM3 aggregate stats are unavailable."
        return empty_stats(database_name, hero_name, warning)
    if "players" not in tables:
        warning = "players table is missing. Hero aggregate stats cannot be linked."
        return empty_stats(database_name, hero_name, warning)

    columns = table_columns(connection, "compiledplayerresults")
    required_columns = {
        "player_id",
        "playedyearandmonth",
        "numberofplayers",
        "gametype_id",
        "bbgroup_id",
        "totalhands",
        "totalamountwonincents",
        "totalrakeincents",
        "totalbbswon",
        "vpiphands",
        "pfrhands",
        "couldvpip",
        "couldpfr",
        "couldthreebet",
        "didthreebet",
        "couldsqueeze",
        "didsqueeze",
        "sawflop",
        "sawshowdown",
        "wonshowdown",
        "wonhandwhensawflop",
        "totalbets",
        "totalcalls",
        "totalpostflopstreetsseen",
        "totalaggressivepostflopstreetsseen",
        "facedthreebetpreflop",
        "foldedtothreebetpreflop",
        "facedfourbetpreflop",
        "foldedtofourbetpreflop",
        "flopcontinuationbetpossible",
        "flopcontinuationbetmade",
        "facingflopcontinuationbet",
        "foldedtoflopcontinuationbet",
    }
    missing_columns = sorted(required_columns - columns)
    if missing_columns:
        warning = f"compiledplayerresults is missing columns: {', '.join(missing_columns)}."
        return empty_stats(database_name, hero_name, warning)

    player = find_hero_player(connection, hero_name)
    if player is None:
        warning = f"Hero aliases {hero_aliases(hero_name)} were not found in players."
        return empty_stats(database_name, hero_name, warning)

    totals = aggregate_player_stats(connection, int(player["player_id"]))
    trend = aggregate_monthly_trend(connection, int(player["player_id"]))
    table_size = aggregate_group_breakdown(connection, int(player["player_id"]), "numberofplayers")
    blind_group = aggregate_group_breakdown(connection, int(player["player_id"]), "bbgroup_id")
    stats = calculated_stats(totals)
    insights = build_stat_insights(stats, totals)

    if stats["total_hands"] < 1000:
        warnings.append("Small sample size for aggregate stats.")
    if stats["fold_to_steal_pct"] is None:
        missing_data.append("Exact Fold to Steal is not mapped yet from this HM3 schema.")
    missing_data.append("Stats are aggregate HM3 counters, not solver outputs.")

    return {
        "report_type": "hm3_player_stats",
        "configured": True,
        "connected": True,
        "database_name": database_name,
        "hero_name": hero_name,
        "hero_player_name": player["playername"],
        "hero_player_id": int(player["player_id"]),
        "stats": stats,
        "raw_counts": {key: totals[key] for key in sorted(totals.keys())},
        "monthly_trend": trend,
        "table_size_breakdown": table_size,
        "blind_group_breakdown": blind_group,
        "insights": insights,
        "coach_priority": build_coach_priority(stats),
        "warnings": warnings,
        "missing_data": missing_data,
        "coach_instruction": (
            "Use these HM3 aggregate stats as the primary overview source. "
            "Use selected hands only to verify hypotheses."
        ),
    }


def empty_stats(database_name: str, hero_name: str, warning: str) -> dict[str, Any]:
    return {
        "report_type": "hm3_player_stats",
        "configured": True,
        "connected": True,
        "database_name": database_name,
        "hero_name": hero_name,
        "stats": {},
        "insights": [],
        "warnings": [warning],
        "missing_data": [warning],
    }


def find_hero_player(connection: sqlite3.Connection, hero_name: str) -> sqlite3.Row | None:
    aliases = [alias.lower() for alias in hero_aliases(hero_name)]
    placeholders = ",".join(["?"] * len(aliases))
    return connection.execute(
        f"""
        SELECT player_id, playername, tourneyhands
        FROM players
        WHERE lower(playername) IN ({placeholders})
        ORDER BY tourneyhands DESC, player_id
        LIMIT 1
        """,
        aliases,
    ).fetchone()


def aggregate_player_stats(connection: sqlite3.Connection, player_id: int) -> dict[str, float]:
    row = connection.execute(
        """
        SELECT
          COALESCE(SUM(totalhands), 0) totalhands,
          COALESCE(SUM(totalamountwonincents), 0) totalamountwonincents,
          COALESCE(SUM(totalrakeincents), 0) totalrakeincents,
          COALESCE(SUM(totalbbswon), 0) totalbbswon,
          COALESCE(SUM(vpiphands), 0) vpiphands,
          COALESCE(SUM(pfrhands), 0) pfrhands,
          COALESCE(SUM(couldvpip), 0) couldvpip,
          COALESCE(SUM(couldpfr), 0) couldpfr,
          COALESCE(SUM(couldthreebet), 0) couldthreebet,
          COALESCE(SUM(didthreebet), 0) didthreebet,
          COALESCE(SUM(couldsqueeze), 0) couldsqueeze,
          COALESCE(SUM(didsqueeze), 0) didsqueeze,
          COALESCE(SUM(sawflop), 0) sawflop,
          COALESCE(SUM(sawshowdown), 0) sawshowdown,
          COALESCE(SUM(wonshowdown), 0) wonshowdown,
          COALESCE(SUM(wonhandwhensawflop), 0) wonhandwhensawflop,
          COALESCE(SUM(totalbets), 0) totalbets,
          COALESCE(SUM(totalcalls), 0) totalcalls,
          COALESCE(SUM(totalpostflopstreetsseen), 0) totalpostflopstreetsseen,
          COALESCE(SUM(totalaggressivepostflopstreetsseen), 0) totalaggressivepostflopstreetsseen,
          COALESCE(SUM(facedthreebetpreflop), 0) facedthreebetpreflop,
          COALESCE(SUM(foldedtothreebetpreflop), 0) foldedtothreebetpreflop,
          COALESCE(SUM(facedfourbetpreflop), 0) facedfourbetpreflop,
          COALESCE(SUM(foldedtofourbetpreflop), 0) foldedtofourbetpreflop,
          COALESCE(SUM(flopcontinuationbetpossible), 0) flopcontinuationbetpossible,
          COALESCE(SUM(flopcontinuationbetmade), 0) flopcontinuationbetmade,
          COALESCE(SUM(facingflopcontinuationbet), 0) facingflopcontinuationbet,
          COALESCE(SUM(foldedtoflopcontinuationbet), 0) foldedtoflopcontinuationbet
        FROM compiledplayerresults
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    return {key: float(row[key] or 0) for key in row.keys()}


def aggregate_monthly_trend(connection: sqlite3.Connection, player_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT playedyearandmonth,
               COALESCE(SUM(totalhands), 0) totalhands,
               COALESCE(SUM(totalbbswon), 0) totalbbswon,
               COALESCE(SUM(totalamountwonincents), 0) totalamountwonincents
        FROM compiledplayerresults
        WHERE player_id = ?
        GROUP BY playedyearandmonth
        ORDER BY playedyearandmonth
        """,
        (player_id,),
    ).fetchall()
    return [
        {
            "period": row["playedyearandmonth"],
            "hands": int(row["totalhands"] or 0),
            "bb100": ratio(row["totalbbswon"], row["totalhands"], scale=100),
            "total_bbs_won": round(float(row["totalbbswon"] or 0), 2),
            "net_won_cents": int(row["totalamountwonincents"] or 0),
        }
        for row in rows
        if row["totalhands"]
    ]


def aggregate_group_breakdown(
    connection: sqlite3.Connection, player_id: int, group_column: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        f"""
        SELECT {group_column} group_value,
               COALESCE(SUM(totalhands), 0) totalhands,
               COALESCE(SUM(totalbbswon), 0) totalbbswon
        FROM compiledplayerresults
        WHERE player_id = ?
        GROUP BY {group_column}
        ORDER BY totalhands DESC
        LIMIT 10
        """,
        (player_id,),
    ).fetchall()
    return [
        {
            "group": row["group_value"],
            "hands": int(row["totalhands"] or 0),
            "bb100": ratio(row["totalbbswon"], row["totalhands"], scale=100),
        }
        for row in rows
        if row["totalhands"]
    ]


def calculated_stats(totals: dict[str, float]) -> dict[str, Any]:
    vpip = pct(totals["vpiphands"], totals["couldvpip"])
    pfr = pct(totals["pfrhands"], totals["couldpfr"])
    return {
        "total_hands": int(totals["totalhands"]),
        "bb100": ratio(totals["totalbbswon"], totals["totalhands"], scale=100),
        "total_bbs_won": round(totals["totalbbswon"], 2),
        "net_won_cents": int(totals["totalamountwonincents"]),
        "rake_cents": int(totals["totalrakeincents"]),
        "vpip_pct": vpip,
        "pfr_pct": pfr,
        "vpip_pfr_gap_pct": round(vpip - pfr, 1) if vpip is not None and pfr is not None else None,
        "three_bet_pct": pct(totals["didthreebet"], totals["couldthreebet"]),
        "squeeze_pct": pct(totals["didsqueeze"], totals["couldsqueeze"]),
        "wtsd_pct": pct(totals["sawshowdown"], totals["sawflop"]),
        "wssd_pct": pct(totals["wonshowdown"], totals["sawshowdown"]),
        "wwsf_pct": pct(totals["wonhandwhensawflop"], totals["sawflop"]),
        "aggression_factor_estimate": ratio(totals["totalbets"], totals["totalcalls"], scale=1),
        "postflop_aggression_pct": pct(
            totals["totalaggressivepostflopstreetsseen"],
            totals["totalpostflopstreetsseen"],
        ),
        "fold_to_3bet_pct": pct(totals["foldedtothreebetpreflop"], totals["facedthreebetpreflop"]),
        "fold_to_4bet_pct": pct(totals["foldedtofourbetpreflop"], totals["facedfourbetpreflop"]),
        "flop_cbet_pct": pct(
            totals["flopcontinuationbetmade"], totals["flopcontinuationbetpossible"]
        ),
        "fold_to_flop_cbet_pct": pct(
            totals["foldedtoflopcontinuationbet"], totals["facingflopcontinuationbet"]
        ),
        "fold_to_steal_pct": None,
    }


def build_stat_insights(stats: dict[str, Any], totals: dict[str, float]) -> list[dict[str, Any]]:
    insights = []
    gap = stats.get("vpip_pfr_gap_pct")
    if gap is not None and gap >= 5:
        insights.append(
            {
                "title": "VPIP/PFR gap",
                "evidence": f"VPIP {stats['vpip_pct']}%, PFR {stats['pfr_pct']}%, gap {gap}%.",
                "coach_angle": (
                    "Check passive flats and limp/call spots. Prefer iso raises and steals."
                ),
                "confidence": "high" if stats["total_hands"] >= 5000 else "medium",
            }
        )
    fold_3bet = stats.get("fold_to_3bet_pct")
    if fold_3bet is not None and fold_3bet < 55:
        insights.append(
            {
                "title": "Low fold to 3bet",
                "evidence": (
                    f"Fold to 3Bet {fold_3bet}% over "
                    f"{int(totals['facedthreebetpreflop'])} faced 3bets."
                ),
                "coach_angle": (
                    "Review 3bet defense versus tight microstakes ranges, especially OOP."
                ),
                "confidence": "medium",
            }
        )
    wtsd = stats.get("wtsd_pct")
    if wtsd is not None and wtsd > 38:
        insights.append(
            {
                "title": "High showdown reach",
                "evidence": f"WTSD {wtsd}% with W$SD {stats.get('wssd_pct')}%.",
                "coach_angle": (
                    "Check hero calls and medium-strength hands versus passive aggression."
                ),
                "confidence": "medium",
            }
        )
    if stats.get("bb100") is not None:
        insights.append(
            {
                "title": "Winrate baseline",
                "evidence": f"bb/100 {stats['bb100']} over {stats['total_hands']} hands.",
                "coach_angle": "Use this as baseline, then find where the EV is leaking by spot.",
                "confidence": "high" if stats["total_hands"] >= 10000 else "medium",
            }
        )
    return insights[:5]


def build_coach_priority(stats: dict[str, Any]) -> list[str]:
    priorities = []
    fold_3bet = stats.get("fold_to_3bet_pct")
    wtsd = stats.get("wtsd_pct")
    gap = stats.get("vpip_pfr_gap_pct")
    if fold_3bet is not None and fold_3bet < 55:
        priorities.append(
            f"Start with 3bet defense: Fold to 3Bet is {fold_3bet}%, likely too sticky."
        )
    if wtsd is not None and wtsd > 38:
        priorities.append(
            f"Review showdown discipline: WTSD is {wtsd}%, check river calls and bluff-catchers."
        )
    if gap is not None and gap >= 5:
        priorities.append(
            f"Review passive preflop gap: VPIP/PFR gap is {gap}%, check flats and limp calls."
        )
    if stats.get("bb100") is not None:
        priorities.append(
            f"Use bb/100 {stats['bb100']} over {stats['total_hands']} hands as the baseline."
        )
    return priorities


def pct(numerator: float, denominator: float) -> float | None:
    return ratio(numerator, denominator, scale=100)


def ratio(numerator: float, denominator: float, scale: float) -> float | None:
    if not denominator:
        return None
    return round((float(numerator) / float(denominator)) * scale, 2)
