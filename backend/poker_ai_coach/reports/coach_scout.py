import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from poker_ai_coach.config import Settings
from poker_ai_coach.db.error_messages import database_open_failure, missing_database_path_warning
from poker_ai_coach.db.hm3_connection import connect_readonly
from poker_ai_coach.db.schema_probe import count_table_rows, list_tables
from poker_ai_coach.reports.hand_review_queue import (
    has_all_in_text,
    normalize_date,
    parse_large_pot,
    table_columns,
)
from poker_ai_coach.reports.hero_aliases import hero_aliases, text_has_hero_alias

SCAN_LIMIT = 50000
REPORT_HAND_LIMIT = 15
LEVEL_BLINDS_RE = re.compile(r"Level[^(]*\(([\d,]+)/([\d,]+)\)", re.IGNORECASE)
SEAT_RE = re.compile(r"Seat\s+(\d+):\s+(.+?)\s+\(([\d,]+)\s+in chips\)", re.IGNORECASE)
BUTTON_RE = re.compile(r"Seat\s+#(\d+)\s+is the button", re.IGNORECASE)
DEALT_RE = re.compile(r"Dealt to\s+(.+?)\s+\[([^\]]+)\]", re.IGNORECASE)


def build_coach_scout_report(settings: Settings) -> dict[str, Any]:
    database_path = settings.hm3_db_path
    if database_path is None:
        warning = missing_database_path_warning()
        return {
            "configured": False,
            "connected": False,
            "hero_name": settings.hero_name,
            "hero_aliases": hero_aliases(settings.hero_name),
            "warnings": [warning],
            "missing_data": [warning],
            "insights": [],
        }

    database_name = Path(database_path).name
    try:
        with connect_readonly(database_path) as connection:
            return build_connected_coach_scout(
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
            "hero_aliases": hero_aliases(settings.hero_name),
            "warnings": warnings,
            "missing_data": warnings,
            "error": error,
            "insights": [],
        }


def build_connected_coach_scout(
    connection: sqlite3.Connection,
    database_name: str,
    hero_name: str,
) -> dict[str, Any]:
    tables = set(list_tables(connection))
    warnings: list[str] = []
    missing_data: list[str] = []
    aliases = hero_aliases(hero_name)

    if "handhistories" not in tables:
        return {
            "configured": True,
            "connected": True,
            "database_name": database_name,
            "hero_name": hero_name,
            "hero_aliases": aliases,
            "warnings": ["handhistories table is missing."],
            "missing_data": ["handhistories table is missing."],
            "insights": [],
        }

    columns = table_columns(connection, "handhistories")
    required_columns = {"handhistory_id", "handhistory", "handtimestamp", "tournament_number"}
    missing_columns = sorted(required_columns - columns)
    if missing_columns:
        warning = f"handhistories is missing columns: {', '.join(missing_columns)}."
        return {
            "configured": True,
            "connected": True,
            "database_name": database_name,
            "hero_name": hero_name,
            "hero_aliases": aliases,
            "warnings": [warning],
            "missing_data": [warning],
            "insights": [],
        }

    total_hands = count_table_rows(connection, "handhistories")
    rows = connection.execute(
        """
        SELECT handhistory_id, handhistory, handtimestamp, tournament_number
        FROM handhistories
        WHERE handhistory IS NOT NULL
          AND TRIM(handhistory) != ''
        ORDER BY handhistory_id DESC
        LIMIT ?
        """,
        (SCAN_LIMIT,),
    ).fetchall()
    if total_hands > len(rows):
        missing_data.append(f"Coach scout scanned latest {len(rows)} of {total_hands} hands.")

    analyzed = [analyze_hand_row(row, hero_name) for row in rows]
    analyzed = [hand for hand in analyzed if hand["has_text"]]

    hero_hands = [hand for hand in analyzed if hand["has_hero"]]
    all_in_hands = [hand for hand in analyzed if hand["is_all_in"]]
    large_pot_hands = [hand for hand in analyzed if hand["large_pot"]]
    hero_all_in_hands = [hand for hand in hero_hands if hand["is_all_in"]]
    hero_large_pot_hands = [hand for hand in hero_hands if hand["large_pot"]]
    hero_all_in_large_pot = [hand for hand in hero_hands if hand["is_all_in"] and hand["large_pot"]]

    hero_action_counts = Counter()
    for hand in hero_hands:
        hero_action_counts.update(hand["hero_actions"])

    position_counts = Counter(
        hand["hero_position"] for hand in hero_hands if hand["hero_position"] is not None
    )
    stack_bands = Counter(stack_band(hand["hero_stack_bb"]) for hand in hero_hands)
    tournament_clusters = tournament_cluster_report(hero_all_in_large_pot or hero_hands)
    top_review_hands = top_hand_candidates(hero_all_in_large_pot or hero_hands or analyzed)
    top_large_pots = sorted(
        [hand for hand in hero_large_pot_hands if hand["pot_size"] is not None],
        key=lambda hand: (hand["pot_size"] or 0, hand["hand_id"]),
        reverse=True,
    )[:REPORT_HAND_LIMIT]

    if not hero_hands:
        missing_data.append(
            f"Hero aliases {aliases} were not found in scanned hand text. "
            "Scout falls back to global all-in and large-pot signals."
        )
    if "error_hands" in tables:
        error_hands = count_table_rows(connection, "error_hands")
    else:
        error_hands = 0
        missing_data.append("error_hands table is missing.")

    insights = build_scout_insights(
        hero_hands=hero_hands,
        all_in_hands=all_in_hands,
        hero_all_in_hands=hero_all_in_hands,
        hero_all_in_large_pot=hero_all_in_large_pot,
        top_large_pots=top_large_pots,
        tournament_clusters=tournament_clusters,
        hero_action_counts=hero_action_counts,
    )

    return {
        "report_type": "coach_scout",
        "configured": True,
        "connected": True,
        "database_name": database_name,
        "hero_name": hero_name,
        "hero_aliases": aliases,
        "scan_limit": SCAN_LIMIT,
        "total_hands": total_hands,
        "scanned_hands": len(analyzed),
        "hero_text_hands": len(hero_hands),
        "all_in_hands": len(all_in_hands),
        "large_pot_hands": len(large_pot_hands),
        "hero_all_in_hands": len(hero_all_in_hands),
        "hero_large_pot_hands": len(hero_large_pot_hands),
        "hero_all_in_large_pot_hands": len(hero_all_in_large_pot),
        "error_hands": error_hands,
        "hero_action_counts": dict(hero_action_counts),
        "hero_position_counts": dict(position_counts),
        "hero_stack_bands": dict(stack_bands),
        "tournament_clusters": tournament_clusters,
        "top_review_hands": top_review_hands,
        "top_large_pots": [hand_summary_for_report(hand) for hand in top_large_pots],
        "insights": insights,
        "warnings": warnings,
        "missing_data": sorted(set(missing_data)),
        "coach_instruction": (
            "Use this report as the primary context. Start with poker insights and exact hand IDs. "
            "Treat data quality as caveat only."
        ),
    }


def analyze_hand_row(row: sqlite3.Row, hero_name: str) -> dict[str, Any]:
    hand_text = str(row["handhistory"] or "")
    hand_date, is_date_unknown = normalize_date(row["handtimestamp"])
    parsed = parse_hand_text(hand_text, hero_name)
    pot_size = parse_large_pot(hand_text)
    return {
        "hand_id": int(row["handhistory_id"]),
        "tournament_number": (
            str(row["tournament_number"]) if row["tournament_number"] is not None else None
        ),
        "hand_date": hand_date,
        "is_date_unknown": is_date_unknown,
        "has_text": bool(hand_text.strip()),
        "has_hero": text_has_hero_alias(hand_text, hero_name),
        "is_all_in": has_all_in_text(hand_text),
        "large_pot": pot_size is not None,
        "pot_size": pot_size,
        **parsed,
    }


def parse_hand_text(hand_text: str, hero_name: str) -> dict[str, Any]:
    lines = hand_text.splitlines()
    button_seat = parse_button_seat(lines)
    seats = parse_seats(lines)
    hero_seat, hero_stack = find_hero_seat_and_stack(seats, hero_name)
    small_blind, big_blind = parse_blinds(lines)
    hero_stack_bb = round(hero_stack / big_blind, 1) if hero_stack and big_blind else None
    hero_position = position_name(hero_seat, button_seat, sorted(seats)) if hero_seat else None
    hero_actions = hero_actions_from_lines(lines, hero_name)
    return {
        "hero_seat": hero_seat,
        "hero_stack": hero_stack,
        "hero_stack_bb": hero_stack_bb,
        "hero_position": hero_position,
        "small_blind": small_blind,
        "big_blind": big_blind,
        "hero_cards_seen": dealt_to_hero_seen(lines, hero_name),
        "hero_actions": hero_actions,
    }


def parse_button_seat(lines: list[str]) -> int | None:
    for line in lines[:12]:
        match = BUTTON_RE.search(line)
        if match:
            return int(match.group(1))
    return None


def parse_seats(lines: list[str]) -> dict[int, tuple[str, int]]:
    seats = {}
    for line in lines[:15]:
        match = SEAT_RE.search(line)
        if not match:
            continue
        seat = int(match.group(1))
        name = match.group(2)
        stack = int(match.group(3).replace(",", ""))
        seats[seat] = (name, stack)
    return seats


def find_hero_seat_and_stack(
    seats: dict[int, tuple[str, int]], hero_name: str
) -> tuple[int | None, int | None]:
    aliases = [alias.lower() for alias in hero_aliases(hero_name)]
    for seat, (name, stack) in seats.items():
        if name.lower() in aliases:
            return seat, stack
    return None, None


def parse_blinds(lines: list[str]) -> tuple[int | None, int | None]:
    for line in lines[:5]:
        match = LEVEL_BLINDS_RE.search(line)
        if not match:
            continue
        small_blind = int(match.group(1).replace(",", ""))
        big_blind = int(match.group(2).replace(",", ""))
        return small_blind, big_blind
    return None, None


def dealt_to_hero_seen(lines: list[str], hero_name: str) -> bool:
    aliases = [alias.lower() for alias in hero_aliases(hero_name)]
    for line in lines:
        match = DEALT_RE.search(line)
        if match and match.group(1).lower() in aliases:
            return True
    return False


def hero_actions_from_lines(lines: list[str], hero_name: str) -> list[str]:
    aliases = [alias.lower() for alias in hero_aliases(hero_name)]
    actions: list[str] = []
    for line in lines:
        lowered = line.lower()
        if not any(lowered.startswith(f"{alias}:") for alias in aliases):
            continue
        if "is all-in" in lowered or "is all in" in lowered:
            if "call" in lowered:
                actions.append("all-in call")
            elif "raise" in lowered or "bet" in lowered:
                actions.append("all-in shove")
            else:
                actions.append("all-in")
        elif " raises " in lowered or lowered.endswith(" raises"):
            actions.append("raise")
        elif " bets " in lowered or lowered.endswith(" bets"):
            actions.append("bet")
        elif " calls " in lowered or lowered.endswith(" calls"):
            actions.append("call")
        elif " folds" in lowered:
            actions.append("fold")
        elif " checks" in lowered:
            actions.append("check")
    return actions


def position_name(
    hero_seat: int | None, button_seat: int | None, active_seats: list[int]
) -> str | None:
    if hero_seat is None or button_seat is None or hero_seat not in active_seats:
        return None
    count = len(active_seats)
    if count < 2:
        return None
    button_index = active_seats.index(button_seat)
    order = active_seats[button_index:] + active_seats[:button_index]
    distance = order.index(hero_seat)
    if distance == 0:
        return "BTN"
    if distance == 1:
        return "SB"
    if distance == 2:
        return "BB"
    if count == 6:
        return ["BTN", "SB", "BB", "UTG", "HJ", "CO"][distance]
    return f"Seat after button +{distance}"


def stack_band(stack_bb_value: Any) -> str:
    if stack_bb_value is None:
        return "unknown"
    stack_bb_float = float(stack_bb_value)
    if stack_bb_float <= 12:
        return "0-12bb"
    if stack_bb_float <= 20:
        return "13-20bb"
    if stack_bb_float <= 30:
        return "21-30bb"
    if stack_bb_float <= 50:
        return "31-50bb"
    return "50bb+"


def tournament_cluster_report(hands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for hand in hands:
        tournament_number = hand.get("tournament_number")
        if tournament_number is None:
            continue
        grouped.setdefault(str(tournament_number), []).append(hand)
    clusters = []
    for tournament_number, tournament_hands in grouped.items():
        sorted_hands = sorted(tournament_hands, key=lambda hand: int(hand["hand_id"]), reverse=True)
        clusters.append(
            {
                "tournament_number": tournament_number,
                "hand_count": len(sorted_hands),
                "hand_ids": [hand["hand_id"] for hand in sorted_hands[:REPORT_HAND_LIMIT]],
                "date": next(
                    (hand["hand_date"] for hand in sorted_hands if hand["hand_date"]), None
                ),
                "main_reasons": cluster_reasons(sorted_hands),
            }
        )
    return sorted(clusters, key=lambda cluster: cluster["hand_count"], reverse=True)[:5]


def cluster_reasons(hands: list[dict[str, Any]]) -> list[str]:
    reasons = Counter()
    for hand in hands:
        if hand["is_all_in"]:
            reasons["all-in"] += 1
        if hand["large_pot"]:
            reasons["large pot"] += 1
        if hand["hero_stack_bb"] is not None:
            reasons[stack_band(hand["hero_stack_bb"])] += 1
    return [reason for reason, _ in reasons.most_common(4)]


def top_hand_candidates(hands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_hands = sorted(hands, key=scout_hand_score, reverse=True)
    return [hand_summary_for_report(hand) for hand in sorted_hands[:REPORT_HAND_LIMIT]]


def scout_hand_score(hand: dict[str, Any]) -> tuple[int, int]:
    score = 0
    if hand["has_hero"]:
        score += 30
    if hand["is_all_in"]:
        score += 35
    if hand["large_pot"]:
        score += 25
    if "all-in call" in hand["hero_actions"]:
        score += 15
    if hand["hero_stack_bb"] is not None and 10 <= float(hand["hero_stack_bb"]) <= 30:
        score += 10
    return score, int(hand["hand_id"])


def hand_summary_for_report(hand: dict[str, Any]) -> dict[str, Any]:
    notes = []
    if hand["is_all_in"]:
        notes.append("all-in")
    if hand["large_pot"]:
        notes.append("large pot")
    if hand["hero_stack_bb"] is not None:
        notes.append(f"{hand['hero_stack_bb']}bb")
    if hand["hero_position"]:
        notes.append(str(hand["hero_position"]))
    return {
        "hand_id": hand["hand_id"],
        "tournament_number": hand["tournament_number"],
        "hand_date": hand["hand_date"],
        "pot_size": hand["pot_size"],
        "hero_stack_bb": hand["hero_stack_bb"],
        "hero_position": hand["hero_position"],
        "hero_actions": hand["hero_actions"],
        "notes": notes,
    }


def build_scout_insights(
    hero_hands: list[dict[str, Any]],
    all_in_hands: list[dict[str, Any]],
    hero_all_in_hands: list[dict[str, Any]],
    hero_all_in_large_pot: list[dict[str, Any]],
    top_large_pots: list[dict[str, Any]],
    tournament_clusters: list[dict[str, Any]],
    hero_action_counts: Counter,
) -> list[dict[str, Any]]:
    insights = []
    hero_sample = len(hero_hands)
    all_in_sample = len(hero_all_in_hands) if hero_sample else len(all_in_hands)
    if all_in_sample:
        insights.append(
            {
                "title": "All-in decision pressure",
                "evidence": (
                    f"{all_in_sample} all-in hands found in "
                    f"{hero_sample or len(all_in_hands)} relevant scanned hands."
                ),
                "hand_ids": [hand["hand_id"] for hand in (hero_all_in_hands or all_in_hands)[:10]],
                "coach_angle": (
                    "Review shove versus call, stack depth, fold equity, bounty pressure, "
                    "and whether the spot is value or spew."
                ),
                "confidence": "high" if all_in_sample >= 50 else "medium",
            }
        )
    if hero_all_in_large_pot:
        insights.append(
            {
                "title": "Large all-in pots",
                "evidence": (
                    f"{len(hero_all_in_large_pot)} hero-related hands are both "
                    "all-in and large pot."
                ),
                "hand_ids": [hand["hand_id"] for hand in hero_all_in_large_pot[:10]],
                "coach_angle": (
                    "These are the highest-value review hands. Mark value target, bluff target, "
                    "SPR, and whether passive aggression should be respected."
                ),
                "confidence": "high" if len(hero_all_in_large_pot) >= 10 else "medium",
            }
        )
    if tournament_clusters:
        top_cluster = tournament_clusters[0]
        if top_cluster["hand_count"] >= 3:
            insights.append(
                {
                    "title": "Tournament story cluster",
                    "evidence": (
                        f"{top_cluster['hand_count']} priority hands are clustered in "
                        f"tournament {top_cluster['tournament_number']}."
                    ),
                    "hand_ids": top_cluster["hand_ids"],
                    "coach_angle": (
                        "Review the tournament as a story, not isolated hands: buildup, "
                        "pressure, stack swings, and possible tilt."
                    ),
                    "confidence": "medium",
                }
            )
    if hero_action_counts:
        calls = hero_action_counts.get("all-in call", 0) + hero_action_counts.get("call", 0)
        shoves = hero_action_counts.get("all-in shove", 0) + hero_action_counts.get("raise", 0)
        if calls > shoves:
            insights.append(
                {
                    "title": "Passive all-in/call bias",
                    "evidence": (
                        f"Hero call-like actions {calls} exceed raise/shove-like actions {shoves}."
                    ),
                    "hand_ids": [
                        hand["hand_id"]
                        for hand in hero_all_in_hands
                        if "all-in call" in hand["hero_actions"]
                    ][:10],
                    "coach_angle": (
                        "Check whether hero is calling off too often instead of choosing "
                        "spots with fold equity."
                    ),
                    "confidence": "medium",
                }
            )
    if top_large_pots:
        insights.append(
            {
                "title": "Top big-pot review list",
                "evidence": f"{len(top_large_pots)} large pots have parsable pot size.",
                "hand_ids": [hand["hand_id"] for hand in top_large_pots[:10]],
                "coach_angle": (
                    "Sort these by pot size and review value extraction, bluff target, "
                    "and medium-strength hand discipline."
                ),
                "confidence": "medium",
            }
        )
    return insights
