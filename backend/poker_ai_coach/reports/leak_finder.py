import sqlite3
from collections import Counter
from pathlib import Path

from poker_ai_coach.config import Settings
from poker_ai_coach.db.error_messages import (
    database_open_failure,
    missing_database_path_warning,
)
from poker_ai_coach.db.hm3_connection import connect_readonly
from poker_ai_coach.db.schema_probe import count_table_rows, list_tables
from poker_ai_coach.models.reports import LeakFinderItem, LeakFinderReport
from poker_ai_coach.reports.hand_review_queue import (
    build_connected_review_queue,
    has_all_in_text,
    normalize_date,
    table_columns,
)
from poker_ai_coach.reports.hero_aliases import hero_aliases, text_has_hero_alias

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"


def pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100, 1)


def confidence_for_sample(total_hands: int) -> str:
    if total_hands >= 100:
        return CONFIDENCE_HIGH
    if total_hands >= 25:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


def safe_count(tables: set[str], connection: sqlite3.Connection, table_name: str) -> int:
    if table_name not in tables:
        return 0
    return count_table_rows(connection, table_name)


def get_hand_rows(
    connection: sqlite3.Connection, tables: set[str]
) -> tuple[list[sqlite3.Row], list[str]]:
    missing_data = []
    if "handhistories" not in tables:
        return [], ["handhistories table is missing."]

    columns = table_columns(connection, "handhistories")
    required_columns = {"handhistory_id", "handhistory", "handtimestamp"}
    missing_columns = sorted(required_columns - columns)
    if missing_columns:
        return [], [f"handhistories is missing columns: {', '.join(missing_columns)}."]

    rows = connection.execute(
        """
        SELECT handhistory_id, handhistory, handtimestamp
        FROM handhistories
        WHERE handhistory IS NOT NULL
          AND TRIM(handhistory) != ''
        ORDER BY handhistory_id
        """
    ).fetchall()
    return rows, missing_data


def tournament_result_coverage(
    connection: sqlite3.Connection,
    tables: set[str],
) -> tuple[int, int, list[str]]:
    missing_data = []
    if "tournaments" not in tables:
        missing_data.append("tournaments table is missing.")
        return 0, 0, missing_data
    if "tournament_players" not in tables:
        missing_data.append("tournament_players table is missing.")
        return safe_count(tables, connection, "tournaments"), 0, missing_data

    tournament_columns = table_columns(connection, "tournaments")
    player_columns = table_columns(connection, "tournament_players")
    if "tournament_id" not in tournament_columns or "tournament_id" not in player_columns:
        missing_data.append("tournament_id is missing from tournament result tables.")
        return safe_count(tables, connection, "tournaments"), 0, missing_data

    total_tournaments = safe_count(tables, connection, "tournaments")
    covered_row = connection.execute(
        """
        SELECT COUNT(DISTINCT t.tournament_id) AS row_count
        FROM tournaments t
        JOIN tournament_players tp ON tp.tournament_id = t.tournament_id
        """
    ).fetchone()
    covered_tournaments = int(covered_row["row_count"])
    return total_tournaments, covered_tournaments, missing_data


def hero_tournament_result_stats(
    connection: sqlite3.Connection,
    tables: set[str],
    hero_name: str,
) -> tuple[dict[str, int | float], list[str]]:
    missing_data: list[str] = []
    required_tables = {"players", "tournaments", "tournament_players"}
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        return {}, [f"Missing tournament result tables: {', '.join(missing_tables)}."]

    player_columns = table_columns(connection, "players")
    tournament_columns = table_columns(connection, "tournaments")
    result_columns = table_columns(connection, "tournament_players")
    required_player_columns = {"player_id", "playername"}
    required_result_columns = {"player_id", "tournament_id"}
    missing_columns = sorted(
        (required_player_columns - player_columns)
        | (required_result_columns - result_columns)
        | ({"tournament_id"} - tournament_columns)
    )
    if missing_columns:
        return {}, [f"Tournament result analysis is missing columns: {', '.join(missing_columns)}."]

    hero_row = None
    for alias in hero_aliases(hero_name):
        hero_row = connection.execute(
            """
            SELECT player_id
            FROM players
            WHERE LOWER(playername) = LOWER(?)
            LIMIT 1
            """,
            (alias,),
        ).fetchone()
        if hero_row is not None:
            break
    if hero_row is None:
        return (
            {},
            [
                "Hero was not found in players using HERO_NAME or fallback alias 'hero', "
                "so tournament result stats are unavailable."
            ],
        )

    money_columns = {
        "buyin_in_cents",
        "rake_in_cents",
        "bounty_in_cents",
    }
    has_money_columns = (
        money_columns <= tournament_columns
        and {
            "winnings_in_cents",
            "total_bounty_in_cents",
        }
        <= result_columns
    )
    finish_expr = (
        "SUM(CASE WHEN tp.finish_position IS NOT NULL AND tp.finish_position > 0 THEN 1 ELSE 0 END)"
        if "finish_position" in result_columns
        else "0"
    )
    cash_expr = (
        "SUM(CASE WHEN COALESCE(tp.winnings_in_cents, 0) + "
        "COALESCE(tp.total_bounty_in_cents, 0) > 0 THEN 1 ELSE 0 END)"
        if has_money_columns
        else "0"
    )
    cost_expr = (
        "SUM(COALESCE(t.buyin_in_cents, 0) + COALESCE(t.rake_in_cents, 0) + "
        "COALESCE(t.bounty_in_cents, 0))"
        if has_money_columns
        else "0"
    )
    return_expr = (
        "SUM(COALESCE(tp.winnings_in_cents, 0) + COALESCE(tp.total_bounty_in_cents, 0))"
        if has_money_columns
        else "0"
    )
    stats_row = connection.execute(
        f"""
        SELECT
          COUNT(*) AS entries,
          {finish_expr} AS finish_rows,
          {cash_expr} AS cashes,
          {cost_expr} AS known_cost,
          {return_expr} AS known_return
        FROM tournament_players tp
        JOIN tournaments t ON t.tournament_id = tp.tournament_id
        WHERE tp.player_id = ?
        """,
        (int(hero_row["player_id"]),),
    ).fetchone()
    stats = {
        "entries": int(stats_row["entries"] or 0),
        "finish_rows": int(stats_row["finish_rows"] or 0),
        "cashes": int(stats_row["cashes"] or 0),
        "known_cost": int(stats_row["known_cost"] or 0),
        "known_return": int(stats_row["known_return"] or 0),
    }
    if stats["entries"] == 0:
        missing_data.append("Hero has no linked tournament_players rows.")
    if not has_money_columns or stats["known_cost"] <= 0:
        missing_data.append(
            "Hero tournament buy-in or winnings values are not usable for ROI analysis."
        )
    if stats["entries"] and stats["finish_rows"] < stats["entries"]:
        missing_data.append(
            f"Hero finish positions exist for {stats['finish_rows']} of "
            f"{stats['entries']} linked tournaments."
        )
    return stats, missing_data


def build_leak_finder_report(settings: Settings) -> LeakFinderReport:
    database_path = settings.hm3_db_path
    if database_path is None:
        warning = missing_database_path_warning()
        return LeakFinderReport(
            configured=False,
            connected=False,
            hero_name=settings.hero_name,
            warnings=[warning],
            missing_data=[warning],
        )

    database_name = Path(database_path).name
    try:
        with connect_readonly(database_path) as connection:
            return build_connected_leak_finder(connection, database_name, settings.hero_name)
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return LeakFinderReport(
            configured=True,
            connected=False,
            database_name=database_name,
            hero_name=settings.hero_name,
            warnings=warnings,
            error=error,
        )


def build_connected_leak_finder(
    connection: sqlite3.Connection,
    database_name: str,
    hero_name: str,
) -> LeakFinderReport:
    tables = set(list_tables(connection))
    rows, missing_data = get_hand_rows(connection, tables)
    total_hands = safe_count(tables, connection, "handhistories")
    text_hand_count = len(rows)
    base_confidence = confidence_for_sample(total_hands)

    leaks = []
    warnings = []
    if total_hands == 0:
        warnings.append("Not enough hand data for leak finder.")

    valid_dates = 0
    invalid_dates = 0
    hero_hits = 0
    all_in_hands = []
    for row in rows:
        hand_text = str(row["handhistory"] or "")
        hand_date, is_unknown = normalize_date(row["handtimestamp"])
        if hand_date and not is_unknown:
            valid_dates += 1
        else:
            invalid_dates += 1
        if text_has_hero_alias(hand_text, hero_name):
            hero_hits += 1
        if has_all_in_text(hand_text):
            all_in_hands.append(int(row["handhistory_id"]))

    if invalid_dates:
        invalid_pct = pct(invalid_dates, text_hand_count)
        leaks.append(
            LeakFinderItem(
                leak_key="invalid_date_coverage",
                leak_name="Invalid date coverage",
                evidence=(
                    f"{invalid_dates} of {text_hand_count} hand texts have unknown or 1970 dates "
                    f"({invalid_pct}%)."
                ),
                confidence=CONFIDENCE_HIGH if text_hand_count >= 25 else CONFIDENCE_MEDIUM,
                recommended_action=(
                    "Use date filters carefully and review HM3 import coverage before "
                    "judging sessions."
                ),
            )
        )
    elif text_hand_count:
        missing_data.append("No invalid hand dates found in sampled hand text.")

    error_hands = safe_count(tables, connection, "error_hands")
    if "error_hands" not in tables:
        missing_data.append("error_hands table is missing.")
    elif error_hands:
        leaks.append(
            LeakFinderItem(
                leak_key="hm3_import_errors",
                leak_name="HM3 import errors",
                evidence=f"{error_hands} error_hands rows found for {total_hands} total hands.",
                confidence=base_confidence,
                recommended_action=(
                    "Treat import-error rows as a data caveat and focus review on linked "
                    "all-in and large-pot hands first."
                ),
            )
        )

    if all_in_hands:
        leaks.append(
            LeakFinderItem(
                leak_key="all_in_review_volume",
                leak_name="All-in review volume",
                evidence=(
                    f"{len(all_in_hands)} of {text_hand_count} hand texts contain all-in language "
                    f"({pct(len(all_in_hands), text_hand_count)}%)."
                ),
                confidence=base_confidence,
                recommended_action=(
                    "Review all-in hands for stack depth, fold equity, bounty pressure, "
                    "and tilt spots."
                ),
                related_hand_ids=all_in_hands[:10],
            )
        )

    if text_hand_count:
        hero_pct = pct(hero_hits, text_hand_count)
        if hero_hits == 0:
            leaks.append(
                LeakFinderItem(
                    leak_key="hero_text_missing",
                    leak_name="Hero missing from hand text",
                    evidence=(
                        f"Hero aliases '{', '.join(hero_aliases(hero_name))}' were not found "
                        f"in {text_hand_count} hand texts."
                    ),
                    confidence=CONFIDENCE_HIGH,
                    recommended_action=(
                        "Check HERO_NAME and site nickname spelling before using reports."
                    ),
                )
            )
        elif hero_pct < 80:
            leaks.append(
                LeakFinderItem(
                    leak_key="hero_text_partial",
                    leak_name="Partial hero text coverage",
                    evidence=(
                        f"Hero aliases '{', '.join(hero_aliases(hero_name))}' appear in "
                        f"{hero_hits} of {text_hand_count} hand texts ({hero_pct}%)."
                    ),
                    confidence=base_confidence,
                    recommended_action=(
                        "Treat text-derived hand categories as partial until nickname "
                        "coverage is fixed."
                    ),
                )
            )
    else:
        missing_data.append("No non-empty hand text found.")

    queue = build_connected_review_queue(connection, database_name, hero_name, limit=50)
    reason_counts = Counter(reason for hand in queue.hands for reason in hand.reasons)
    queue_size = len(queue.hands)
    for reason, count in sorted(reason_counts.items()):
        if reason in {"valid date", "hero name"}:
            continue
        related_hand_ids = [hand.hand_id for hand in queue.hands if reason in hand.reasons][:10]
        leaks.append(
            LeakFinderItem(
                leak_key=f"review_category_{reason.replace(' ', '_').replace('-', '_').lower()}",
                leak_name=f"Review category: {reason}",
                evidence=(
                    f"{count} of {queue_size} selected review hands were tagged as '{reason}'."
                ),
                confidence=CONFIDENCE_MEDIUM if count >= 3 else CONFIDENCE_LOW,
                recommended_action=(
                    "Review these hands for stack depth, pot size, value target, "
                    "fold equity, and tilt risk before making a strategic conclusion."
                ),
                related_hand_ids=related_hand_ids,
            )
        )

    tournament_counts = Counter(
        hand.tournament_number for hand in queue.hands if hand.tournament_number
    )
    if tournament_counts and queue_size:
        tournament_number, count = tournament_counts.most_common(1)[0]
        if count >= 5:
            related_hand_ids = [
                hand.hand_id for hand in queue.hands if hand.tournament_number == tournament_number
            ][:10]
            leaks.append(
                LeakFinderItem(
                    leak_key="selected_tournament_cluster",
                    leak_name="Selected tournament cluster",
                    evidence=(
                        f"{count} of {queue_size} selected review hands came from "
                        f"tournament {tournament_number}."
                    ),
                    confidence=CONFIDENCE_MEDIUM,
                    recommended_action=(
                        "Review this tournament as one story: early chips, big pots, "
                        "all-ins, and the bust or late-stage pressure spots."
                    ),
                    related_hand_ids=related_hand_ids,
                )
            )

    total_tournaments, covered_tournaments, coverage_missing_data = tournament_result_coverage(
        connection, tables
    )
    missing_data.extend(coverage_missing_data)
    if total_tournaments and covered_tournaments < total_tournaments:
        leaks.append(
            LeakFinderItem(
                leak_key="tournament_result_coverage",
                leak_name="Tournament result coverage",
                evidence=(
                    f"{covered_tournaments} of {total_tournaments} tournaments have matching "
                    "tournament_players rows."
                ),
                confidence=CONFIDENCE_MEDIUM,
                recommended_action=(
                    "Do not overread tournament ROI or finish data until result coverage "
                    "is complete."
                ),
            )
        )

    hero_result_stats, result_missing_data = hero_tournament_result_stats(
        connection, tables, hero_name
    )
    missing_data.extend(result_missing_data)
    entries = int(hero_result_stats.get("entries", 0))
    known_cost = int(hero_result_stats.get("known_cost", 0))
    known_return = int(hero_result_stats.get("known_return", 0))
    if entries >= 20 and known_cost > 0:
        net = known_return - known_cost
        roi = pct(net, known_cost)
        if roi < -20:
            leaks.append(
                LeakFinderItem(
                    leak_key="tournament_result_pressure",
                    leak_name="Tournament result pressure",
                    evidence=(
                        f"Hero has {entries} linked tournaments with known cost "
                        f"{known_cost} cents, known return {known_return} cents, "
                        f"net {net} cents, ROI {roi}%."
                    ),
                    confidence=CONFIDENCE_LOW if entries < 100 else CONFIDENCE_MEDIUM,
                    recommended_action=(
                        "Treat this as variance-aware pressure, not proof of a leak. "
                        "Review all-in and large-pot hands before changing strategy."
                    ),
                )
            )

    if not leaks:
        warnings.append("No supported leak signals found yet.")

    return LeakFinderReport(
        configured=True,
        connected=True,
        database_name=database_name,
        hero_name=hero_name,
        total_hands=total_hands,
        leaks=leaks,
        missing_data=sorted(set(missing_data)),
        warnings=warnings,
    )
