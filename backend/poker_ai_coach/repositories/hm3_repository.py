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
from poker_ai_coach.models.hands import HandSummary
from poker_ai_coach.models.tournaments import TournamentHands, TournamentList, TournamentSummary
from poker_ai_coach.reports.hand_review_queue import (
    get_error_hand_ids,
    normalize_date,
    selected_reasons,
    table_columns,
)

TOURNAMENT_LIMIT_MAX = 500
TOURNAMENT_HAND_LIMIT_MAX = 500


def get_tournaments(
    settings: Settings,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    only_with_errors: bool = False,
    limit: int = 100,
) -> TournamentList:
    database_path = settings.hm3_db_path
    if database_path is None:
        return TournamentList(
            configured=False,
            connected=False,
            warnings=[missing_database_path_warning()],
        )

    database_name = Path(database_path).name
    try:
        with connect_readonly(database_path) as connection:
            return get_connected_tournaments(
                connection=connection,
                database_name=database_name,
                date_from=date_from,
                date_to=date_to,
                search=search,
                only_with_errors=only_with_errors,
                limit=limit,
            )
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return TournamentList(
            configured=True,
            connected=False,
            database_name=database_name,
            warnings=warnings,
            error=error,
        )


def get_tournament_hands(
    settings: Settings,
    tournament_number: str,
    limit: int = 100,
) -> TournamentHands:
    database_path = settings.hm3_db_path
    if database_path is None:
        return TournamentHands(
            configured=False,
            connected=False,
            tournament_number=tournament_number,
            warnings=[missing_database_path_warning()],
        )

    database_name = Path(database_path).name
    try:
        with connect_readonly(database_path) as connection:
            return get_connected_tournament_hands(
                connection=connection,
                database_name=database_name,
                tournament_number=tournament_number,
                limit=limit,
            )
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return TournamentHands(
            configured=True,
            connected=False,
            tournament_number=tournament_number,
            database_name=database_name,
            warnings=warnings,
            error=error,
        )


def get_connected_tournaments(
    connection: sqlite3.Connection,
    database_name: str,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    only_with_errors: bool = False,
    limit: int = 100,
) -> TournamentList:
    warnings: list[str] = []
    tables = set(list_tables(connection))
    if "tournaments" not in tables and "handhistories" not in tables:
        return TournamentList(
            configured=True,
            connected=True,
            database_name=database_name,
            warnings=["tournaments and handhistories tables are missing."],
        )

    tournament_rows = _read_tournament_rows(connection, tables, warnings)
    if "handhistories" not in tables:
        warnings.append("handhistories table is missing; hand counts and dates are unavailable.")
    elif "tournament_number" not in table_columns(connection, "handhistories"):
        warnings.append("handhistories.tournament_number is missing; hand counts are unavailable.")

    if "error_hands" not in tables:
        warnings.append("error_hands table is missing; error counts are unavailable.")

    hand_coverage = _get_tournament_hand_coverage_map(connection, tables)
    error_counts = _get_tournament_error_count_map(connection, tables, warnings)
    tournaments = [
        _build_tournament_summary(row, hand_coverage, error_counts) for row in tournament_rows
    ]
    tournaments = _apply_tournament_filters(
        tournaments=tournaments,
        date_from=date_from,
        date_to=date_to,
        search=search,
        only_with_errors=only_with_errors,
        warnings=warnings,
    )
    tournaments.sort(
        key=lambda item: (item.last_hand_date or "", item.tournament_number),
        reverse=True,
    )
    safe_limit = min(max(limit, 1), TOURNAMENT_LIMIT_MAX)

    if not tournaments:
        warnings.append("No tournaments matched the current filters.")

    return TournamentList(
        configured=True,
        connected=True,
        database_name=database_name,
        tournaments=tournaments[:safe_limit],
        warnings=_unique_warnings(warnings),
    )


def get_connected_tournament_hands(
    connection: sqlite3.Connection,
    database_name: str,
    tournament_number: str,
    limit: int = 100,
) -> TournamentHands:
    warnings: list[str] = []
    tables = set(list_tables(connection))
    if "handhistories" not in tables:
        return TournamentHands(
            configured=True,
            connected=True,
            tournament_number=tournament_number,
            database_name=database_name,
            warnings=["handhistories table is missing."],
        )

    columns = table_columns(connection, "handhistories")
    required_columns = {"handhistory_id", "handhistory", "handtimestamp", "tournament_number"}
    missing_columns = sorted(required_columns - columns)
    if missing_columns:
        return TournamentHands(
            configured=True,
            connected=True,
            tournament_number=tournament_number,
            database_name=database_name,
            warnings=[f"handhistories is missing columns: {', '.join(missing_columns)}."],
        )

    error_hand_ids = get_error_hand_ids(connection, tables)
    safe_limit = min(max(limit, 1), TOURNAMENT_HAND_LIMIT_MAX)
    rows = connection.execute(
        """
        SELECT handhistory_id, handhistory, handtimestamp, tournament_number
        FROM handhistories
        WHERE CAST(tournament_number AS TEXT) = ?
          AND handhistory IS NOT NULL
          AND TRIM(handhistory) != ''
        ORDER BY handhistory_id DESC
        LIMIT ?
        """,
        (tournament_number, safe_limit),
    ).fetchall()

    hands = [
        _build_tournament_hand_summary(row, error_hand_ids)
        for row in rows
        if str(row["handhistory"] or "").strip()
    ]
    if not hands:
        warnings.append("No hands were found for this tournament.")

    return TournamentHands(
        configured=True,
        connected=True,
        tournament_number=tournament_number,
        database_name=database_name,
        hands=hands,
        warnings=warnings,
    )


def _read_tournament_rows(
    connection: sqlite3.Connection,
    tables: set[str],
    warnings: list[str],
) -> list[dict[str, Any]]:
    if "tournaments" in tables:
        columns = table_columns(connection, "tournaments")
        if "tournament_number" in columns:
            select_columns = [
                "tournament_number",
                "first_hand_timestamp",
                "last_hand_timestamp",
                "buyin_in_cents",
                "rake_in_cents",
                "bounty_in_cents",
                "number_of_entrants",
            ]
            present_columns = [column for column in select_columns if column in columns]
            quoted_columns = ", ".join(quote_identifier(column) for column in present_columns)
            rows = connection.execute(
                f"""
                SELECT {quoted_columns}
                FROM tournaments
                WHERE tournament_number IS NOT NULL
                ORDER BY tournament_number DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]
        warnings.append("tournaments.tournament_number is missing; using handhistories fallback.")
    else:
        warnings.append("tournaments table is missing; using handhistories fallback.")

    if "handhistories" not in tables:
        return []
    columns = table_columns(connection, "handhistories")
    if "tournament_number" not in columns:
        return []
    rows = connection.execute(
        """
        SELECT DISTINCT tournament_number
        FROM handhistories
        WHERE tournament_number IS NOT NULL
        ORDER BY tournament_number DESC
        """
    ).fetchall()
    return [{"tournament_number": row["tournament_number"]} for row in rows]


def _build_tournament_summary(
    row: dict[str, Any],
    hand_coverage: dict[str, tuple[int, str | None, str | None, bool]],
    error_counts: dict[str, int],
) -> TournamentSummary:
    tournament_number = str(row["tournament_number"])
    hand_count, first_date, last_date, has_unknown_dates = hand_coverage.get(
        tournament_number,
        (0, None, None, True),
    )
    table_first_date, table_first_unknown = _normalize_optional_date(row, "first_hand_timestamp")
    table_last_date, table_last_unknown = _normalize_optional_date(row, "last_hand_timestamp")
    if first_date is None:
        first_date = table_first_date
    if last_date is None:
        last_date = table_last_date

    error_count = error_counts.get(tournament_number, 0)
    is_date_unknown = (
        first_date is None
        or last_date is None
        or has_unknown_dates
        or table_first_unknown
        or table_last_unknown
    )

    return TournamentSummary(
        tournament_number=tournament_number,
        first_hand_date=first_date,
        last_hand_date=last_date,
        is_date_unknown=is_date_unknown,
        buyin_in_cents=_optional_int(row.get("buyin_in_cents")),
        rake_in_cents=_optional_int(row.get("rake_in_cents")),
        bounty_in_cents=_optional_int(row.get("bounty_in_cents")),
        entrants=_optional_int(row.get("number_of_entrants")),
        hand_count=hand_count,
        error_count=error_count,
    )


def _get_tournament_hand_coverage_map(
    connection: sqlite3.Connection,
    tables: set[str],
) -> dict[str, tuple[int, str | None, str | None, bool]]:
    if "handhistories" not in tables:
        return {}
    columns = table_columns(connection, "handhistories")
    if "tournament_number" not in columns:
        return {}
    if "handtimestamp" not in columns:
        rows = connection.execute(
            """
            SELECT CAST(tournament_number AS TEXT) AS tournament_number,
                   COUNT(*) AS hand_count
            FROM handhistories
            WHERE tournament_number IS NOT NULL
            GROUP BY CAST(tournament_number AS TEXT)
            """
        ).fetchall()
        return {
            str(row["tournament_number"]): (int(row["hand_count"]), None, None, True)
            for row in rows
        }

    rows = connection.execute(
        """
        SELECT tournament_number, handtimestamp
        FROM handhistories
        WHERE tournament_number IS NOT NULL
        """,
    ).fetchall()
    coverage: dict[str, tuple[int, list[str], bool]] = {}
    for row in rows:
        tournament_number = str(row["tournament_number"])
        hand_count, valid_dates, has_unknown_dates = coverage.get(
            tournament_number,
            (0, [], False),
        )
        hand_date, is_unknown = normalize_date(row["handtimestamp"])
        hand_count += 1
        if hand_date is None:
            has_unknown_dates = True
        else:
            valid_dates.append(hand_date)
            has_unknown_dates = has_unknown_dates or is_unknown
        coverage[tournament_number] = (hand_count, valid_dates, has_unknown_dates)

    return {
        tournament_number: (
            hand_count,
            min(valid_dates) if valid_dates else None,
            max(valid_dates) if valid_dates else None,
            has_unknown_dates or not valid_dates,
        )
        for tournament_number, (hand_count, valid_dates, has_unknown_dates) in coverage.items()
    }


def _get_tournament_error_count_map(
    connection: sqlite3.Connection,
    tables: set[str],
    warnings: list[str],
) -> dict[str, int]:
    if "error_hands" not in tables:
        return {}

    error_columns = table_columns(connection, "error_hands")
    if "handhistory_id" in error_columns and "handhistories" in tables:
        hand_columns = table_columns(connection, "handhistories")
        if {"handhistory_id", "tournament_number"}.issubset(hand_columns):
            rows = connection.execute(
                """
                SELECT CAST(h.tournament_number AS TEXT) AS tournament_number,
                       COUNT(*) AS error_count
                FROM error_hands AS e
                JOIN handhistories AS h
                  ON h.handhistory_id = e.handhistory_id
                WHERE h.tournament_number IS NOT NULL
                GROUP BY CAST(h.tournament_number AS TEXT)
                """,
            ).fetchall()
            return {str(row["tournament_number"]): int(row["error_count"]) for row in rows}

    if "tournament_number" in error_columns:
        rows = connection.execute(
            """
            SELECT CAST(tournament_number AS TEXT) AS tournament_number,
                   COUNT(*) AS error_count
            FROM error_hands
            WHERE tournament_number IS NOT NULL
            GROUP BY CAST(tournament_number AS TEXT)
            """,
        ).fetchall()
        return {str(row["tournament_number"]): int(row["error_count"]) for row in rows}

    warnings.append("error_hands cannot be linked to tournaments.")
    return {}


def _apply_tournament_filters(
    tournaments: list[TournamentSummary],
    date_from: str | None,
    date_to: str | None,
    search: str | None,
    only_with_errors: bool,
    warnings: list[str],
) -> list[TournamentSummary]:
    filtered = tournaments
    if search:
        needle = search.strip().lower()
        filtered = [
            tournament for tournament in filtered if needle in tournament.tournament_number.lower()
        ]

    if only_with_errors:
        filtered = [tournament for tournament in filtered if tournament.error_count > 0]

    if date_from or date_to:
        hidden_unknown = 0
        date_filtered = []
        for tournament in filtered:
            if tournament.first_hand_date is None or tournament.last_hand_date is None:
                hidden_unknown += 1
                continue
            if date_from and tournament.last_hand_date < date_from:
                continue
            if date_to and tournament.first_hand_date > date_to:
                continue
            date_filtered.append(tournament)
        if hidden_unknown:
            warnings.append("Tournaments with unknown dates are hidden by date filters.")
        filtered = date_filtered

    return filtered


def _build_tournament_hand_summary(
    row: sqlite3.Row,
    error_hand_ids: set[int],
) -> HandSummary:
    hand_id = int(row["handhistory_id"])
    hand_text = str(row["handhistory"] or "")
    hand_date, is_date_unknown = normalize_date(row["handtimestamp"])
    is_error_hand = hand_id in error_hand_ids
    reasons = selected_reasons(hand_text, "__hero_not_used__", hand_date, is_error_hand)
    if not reasons:
        reasons = ["tournament hand"]
    tournament_number = row["tournament_number"]
    return HandSummary(
        hand_id=hand_id,
        tournament_number=str(tournament_number) if tournament_number is not None else None,
        hand_date=hand_date,
        is_date_unknown=is_date_unknown,
        reasons=reasons,
        source="error_hands" if is_error_hand else "handhistories",
    )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_optional_date(row: dict[str, Any], key: str) -> tuple[str | None, bool]:
    if key not in row:
        return None, False
    return normalize_date(row.get(key))


def _unique_warnings(warnings: list[str]) -> list[str]:
    return list(dict.fromkeys(warnings))
