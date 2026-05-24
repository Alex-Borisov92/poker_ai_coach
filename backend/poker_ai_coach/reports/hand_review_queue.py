import re
import sqlite3
from pathlib import Path
from typing import Any

from poker_ai_coach.config import Settings
from poker_ai_coach.db.error_messages import (
    database_open_failure,
    missing_database_path_warning,
)
from poker_ai_coach.db.hm3_connection import connect_readonly
from poker_ai_coach.db.schema_probe import list_tables, quote_identifier
from poker_ai_coach.models.hands import HandDetail, HandReviewQueue, HandSummary
from poker_ai_coach.reports.hero_aliases import text_has_hero_alias

MAX_CANDIDATES = 1000
LARGE_POT_MIN_CHIPS = 5000
ALL_IN_PATTERNS = ("all-in", "all in", "allin")
POT_PATTERN = re.compile(r"(?:total pot|main pot|pot)[:\s]+\$?([0-9][0-9,\.]*)", re.I)


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({quote_identifier(table_name)})").fetchall()
    return {row["name"] for row in rows}


def normalize_date(raw_date: Any) -> tuple[str | None, bool]:
    if raw_date is None:
        return None, True
    text = str(raw_date).strip()
    if not text:
        return None, True
    hand_date = text[:10]
    if hand_date == "1970-01-01":
        return None, True
    if len(hand_date) == 10 and hand_date[4] == "-" and hand_date[7] == "-":
        return hand_date, False
    return None, True


def has_all_in_text(hand_text: str) -> bool:
    lowered = hand_text.lower()
    return any(pattern in lowered for pattern in ALL_IN_PATTERNS)


def parse_large_pot(hand_text: str) -> int | None:
    match = POT_PATTERN.search(hand_text)
    if match is None:
        return None
    raw_value = match.group(1).replace(",", "")
    try:
        pot_value = int(float(raw_value))
    except ValueError:
        return None
    if pot_value >= LARGE_POT_MIN_CHIPS:
        return pot_value
    return None


def get_error_hand_ids(connection: sqlite3.Connection, tables: set[str]) -> set[int]:
    if "error_hands" not in tables:
        return set()
    columns = table_columns(connection, "error_hands")
    if "handhistory_id" not in columns:
        return set()

    rows = connection.execute(
        """
        SELECT handhistory_id
        FROM error_hands
        WHERE handhistory_id IS NOT NULL
        """
    ).fetchall()
    return {int(row["handhistory_id"]) for row in rows}


def selected_reasons(
    hand_text: str,
    hero_name: str,
    hand_date: str | None,
    is_error_hand: bool,
) -> list[str]:
    reasons = []
    if text_has_hero_alias(hand_text, hero_name):
        reasons.append("hero name")
    if has_all_in_text(hand_text):
        reasons.append("all-in")
    if hand_date is not None:
        reasons.append("valid date")
    if is_error_hand:
        reasons.append("HM3 import error")
    if parse_large_pot(hand_text) is not None:
        reasons.append("large pot")
    return reasons


def hand_score(summary: HandSummary) -> tuple[int, str, int]:
    score = 0
    if "HM3 import error" in summary.reasons:
        score += 80
    if "all-in" in summary.reasons:
        score += 30
    if "large pot" in summary.reasons:
        score += 20
    if "hero name" in summary.reasons:
        score += 10
    if "valid date" in summary.reasons:
        score += 1
    return score, summary.hand_date or "", summary.hand_id


def build_hand_summary(
    row: sqlite3.Row,
    hero_name: str,
    error_hand_ids: set[int],
) -> HandSummary | None:
    hand_id = int(row["handhistory_id"])
    hand_text = str(row["handhistory"] or "")
    if not hand_text.strip():
        return None

    hand_date, is_date_unknown = normalize_date(row["handtimestamp"])
    is_error_hand = hand_id in error_hand_ids
    reasons = selected_reasons(hand_text, hero_name, hand_date, is_error_hand)
    if not reasons:
        return None

    tournament_number = row["tournament_number"]
    return HandSummary(
        hand_id=hand_id,
        tournament_number=str(tournament_number) if tournament_number is not None else None,
        hand_date=hand_date,
        is_date_unknown=is_date_unknown,
        reasons=reasons,
        source="error_hands" if is_error_hand else "handhistories",
    )


def build_review_queue(settings: Settings, limit: int = 50) -> HandReviewQueue:
    database_path = settings.hm3_db_path
    if database_path is None:
        return HandReviewQueue(
            configured=False,
            connected=False,
            warnings=[missing_database_path_warning()],
        )

    database_name = Path(database_path).name
    try:
        with connect_readonly(database_path) as connection:
            return build_connected_review_queue(
                connection=connection,
                database_name=database_name,
                hero_name=settings.hero_name,
                limit=limit,
            )
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return HandReviewQueue(
            configured=True,
            connected=False,
            database_name=database_name,
            warnings=warnings,
            error=error,
        )


def build_connected_review_queue(
    connection: sqlite3.Connection,
    database_name: str,
    hero_name: str,
    limit: int,
) -> HandReviewQueue:
    warnings = []
    tables = set(list_tables(connection))
    if "handhistories" not in tables:
        return HandReviewQueue(
            configured=True,
            connected=True,
            database_name=database_name,
            warnings=["handhistories table is missing."],
        )

    columns = table_columns(connection, "handhistories")
    required_columns = {"handhistory_id", "handhistory", "handtimestamp", "tournament_number"}
    missing_columns = sorted(required_columns - columns)
    if missing_columns:
        return HandReviewQueue(
            configured=True,
            connected=True,
            database_name=database_name,
            warnings=[f"handhistories is missing columns: {', '.join(missing_columns)}."],
        )

    if "error_hands" not in tables:
        warnings.append("error_hands table is missing.")
    elif "handhistory_id" not in table_columns(connection, "error_hands"):
        warnings.append("error_hands.handhistory_id is missing; import error markers unavailable.")

    error_hand_ids = get_error_hand_ids(connection, tables)
    rows = connection.execute(
        """
        SELECT handhistory_id, handhistory, handtimestamp, tournament_number
        FROM handhistories
        WHERE handhistory IS NOT NULL
          AND TRIM(handhistory) != ''
        ORDER BY handhistory_id DESC
        LIMIT ?
        """,
        (MAX_CANDIDATES,),
    ).fetchall()

    hands = [
        summary
        for row in rows
        if (summary := build_hand_summary(row, hero_name, error_hand_ids)) is not None
    ]
    hands.sort(key=hand_score, reverse=True)

    if not hands:
        warnings.append("No review hands matched the initial selection rules.")

    return HandReviewQueue(
        configured=True,
        connected=True,
        database_name=database_name,
        hands=hands[:limit],
        warnings=warnings,
    )


def get_hand_detail(settings: Settings, hand_id: int) -> HandDetail:
    database_path = settings.hm3_db_path
    if database_path is None:
        return HandDetail(
            configured=False,
            connected=False,
            hand_id=hand_id,
            warnings=[missing_database_path_warning()],
        )

    try:
        with connect_readonly(database_path) as connection:
            return get_connected_hand_detail(connection, hand_id)
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return HandDetail(
            configured=True,
            connected=False,
            hand_id=hand_id,
            warnings=warnings,
            error=error,
        )


def get_connected_hand_detail(connection: sqlite3.Connection, hand_id: int) -> HandDetail:
    tables = set(list_tables(connection))
    if "handhistories" not in tables:
        return HandDetail(
            configured=True,
            connected=True,
            hand_id=hand_id,
            warnings=["handhistories table is missing."],
            error="Hand not found.",
        )

    columns = table_columns(connection, "handhistories")
    required_columns = {"handhistory_id", "handhistory", "handtimestamp", "tournament_number"}
    missing_columns = sorted(required_columns - columns)
    if missing_columns:
        return HandDetail(
            configured=True,
            connected=True,
            hand_id=hand_id,
            warnings=[f"handhistories is missing columns: {', '.join(missing_columns)}."],
            error="Hand not found.",
        )

    row = connection.execute(
        """
        SELECT handhistory_id, handhistory, handtimestamp, tournament_number
        FROM handhistories
        WHERE handhistory_id = ?
        LIMIT 1
        """,
        (hand_id,),
    ).fetchone()
    if row is None:
        return HandDetail(
            configured=True,
            connected=True,
            hand_id=hand_id,
            error="Hand not found.",
        )

    hand_date, is_date_unknown = normalize_date(row["handtimestamp"])
    error_hand_ids = get_error_hand_ids(connection, tables)
    tournament_number = row["tournament_number"]
    return HandDetail(
        configured=True,
        connected=True,
        hand_id=int(row["handhistory_id"]),
        tournament_number=str(tournament_number) if tournament_number is not None else None,
        hand_date=hand_date,
        is_date_unknown=is_date_unknown,
        source="error_hands" if hand_id in error_hand_ids else "handhistories",
        hand_text=str(row["handhistory"] or ""),
    )
