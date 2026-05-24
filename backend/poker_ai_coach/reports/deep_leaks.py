from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from poker_ai_coach.config import Settings
from poker_ai_coach.db.error_messages import database_open_failure, missing_database_path_warning
from poker_ai_coach.db.hm3_connection import connect_readonly
from poker_ai_coach.db.schema_probe import list_tables
from poker_ai_coach.models.training import TrainingLeak, TrainingStudyItem
from poker_ai_coach.reports.coach_scout import (
    analyze_hand_row,
    hand_summary_for_report,
    parse_hand_text,
)
from poker_ai_coach.reports.hand_review_queue import get_connected_hand_detail, table_columns
from poker_ai_coach.reports.hm3_player_stats import (
    aggregate_monthly_trend,
    calculated_stats,
    find_hero_player,
)

DEEP_HAND_LIMIT = 10
MONTHLY_REQUIRED_COLUMNS = {
    "player_id",
    "playedyearandmonth",
    "totalhands",
    "totalbbswon",
    "totalamountwonincents",
    "totalrakeincents",
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


def get_monthly_hm3_stats(settings: Settings, period: str | None = None) -> dict[str, Any]:
    database_path = settings.hm3_db_path
    if database_path is None:
        warning = missing_database_path_warning()
        return {"connected": False, "warnings": [warning], "error": warning}
    database_name = Path(database_path).name
    try:
        with connect_readonly(database_path) as connection:
            tables = set(list_tables(connection))
            if "compiledplayerresults" not in tables or "players" not in tables:
                return {
                    "connected": True,
                    "database_name": database_name,
                    "warnings": ["compiledplayerresults or players table is missing."],
                    "stats": {},
                }
            columns = table_columns(connection, "compiledplayerresults")
            missing = sorted(MONTHLY_REQUIRED_COLUMNS - columns)
            if missing:
                return {
                    "connected": True,
                    "database_name": database_name,
                    "warnings": [
                        f"compiledplayerresults is missing columns: {', '.join(missing)}.",
                    ],
                    "stats": {},
                }
            player = find_hero_player(connection, settings.hero_name)
            if player is None:
                return {
                    "connected": True,
                    "database_name": database_name,
                    "warnings": ["Hero was not found in players."],
                    "stats": {},
                }
            player_id = int(player["player_id"])
            trend = aggregate_monthly_trend(connection, player_id)
            selected_period = normalize_period(period) or latest_period(trend)
            totals = aggregate_player_month(connection, player_id, selected_period)
            return {
                "connected": True,
                "database_name": database_name,
                "hero_name": settings.hero_name,
                "hero_player_name": player["playername"],
                "period": selected_period,
                "stats": calculated_stats(totals) if totals["totalhands"] else {},
                "raw_counts": totals,
                "monthly_trend": trend,
                "warnings": [] if selected_period else ["No monthly HM3 aggregate period found."],
            }
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return {
            "connected": False,
            "database_name": database_name,
            "warnings": warnings,
            "error": error,
        }


def get_hm3_period_stats(
    settings: Settings,
    period: str = "latest_valid_week",
) -> dict[str, Any]:
    database_path = settings.hm3_db_path
    if database_path is None:
        warning = missing_database_path_warning()
        return {"connected": False, "warnings": [warning], "error": warning}
    database_name = Path(database_path).name
    try:
        with connect_readonly(database_path) as connection:
            tables = set(list_tables(connection))
            if "handhistories" not in tables:
                return {
                    "connected": True,
                    "database_name": database_name,
                    "warnings": ["handhistories table is missing."],
                    "stats": {},
                }
            columns = table_columns(connection, "handhistories")
            required = {"handhistory_id", "handhistory", "handtimestamp", "tournament_number"}
            missing = sorted(required - columns)
            if missing:
                return {
                    "connected": True,
                    "database_name": database_name,
                    "warnings": [f"handhistories is missing columns: {', '.join(missing)}."],
                    "stats": {},
                }
            start_date, end_date = resolve_period_range(connection, period)
            if start_date is None or end_date is None:
                return {
                    "connected": True,
                    "database_name": database_name,
                    "period": period,
                    "warnings": ["No valid non-1970 hand dates found."],
                    "stats": {},
                }
            stats = aggregate_hand_period(connection, settings.hero_name, start_date, end_date)
            month_proxy = get_monthly_hm3_stats(settings, start_date.strftime("%Y%m"))
            hands = get_candidate_hands_for_leak(
                settings,
                "large_pot_quality",
                start_date.strftime("%Y%m"),
                8,
            ).get("hands", [])
            filtered_hands = [
                hand
                for hand in hands
                if hand.get("hand_date")
                and start_date.isoformat() <= hand["hand_date"] <= end_date.isoformat()
            ][:8]
            return {
                "connected": True,
                "database_name": database_name,
                "period": period,
                "date_from": start_date.isoformat(),
                "date_to": end_date.isoformat(),
                "stats": stats,
                "monthly_proxy": month_proxy.get("stats", {}),
                "monthly_proxy_period": month_proxy.get("period"),
                "candidate_hands": filtered_hands,
                "warnings": [
                    (
                        "HM3 aggregate VPIP/PFR/3Bet stats are monthly in compiledplayerresults. "
                        "This weekly report uses handhistories counts and selected hands, with "
                        "monthly aggregate stats only as a proxy."
                    )
                ],
            }
    except Exception as exc:
        warnings, error = database_open_failure(database_path, exc)
        return {
            "connected": False,
            "database_name": database_name,
            "warnings": warnings,
            "error": error,
        }


def find_stat_leaks(
    settings: Settings,
    period: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    monthly = get_monthly_hm3_stats(settings, period)
    stats = monthly.get("stats", {})
    raw_counts = monthly.get("raw_counts", {})
    leaks = build_stat_leaks(stats, raw_counts)
    hands_by_key = {
        leak.leak_key: get_candidate_hands_for_leak(settings, leak.leak_key, period, 5).get(
            "hands", []
        )
        for leak in leaks[:limit]
    }
    for leak in leaks:
        hand_ids = [int(hand["hand_id"]) for hand in hands_by_key.get(leak.leak_key, [])]
        leak.related_hand_ids = hand_ids[:DEEP_HAND_LIMIT]
    return {
        "connected": monthly.get("connected", False),
        "database_name": monthly.get("database_name"),
        "period": monthly.get("period"),
        "stats": stats,
        "leaks": [leak.model_dump() for leak in leaks[:limit]],
        "warnings": monthly.get("warnings", []),
    }


def resolve_period_range(
    connection,
    period: str,
) -> tuple[date | None, date | None]:
    normalized = str(period or "latest_valid_week").lower()
    latest = latest_valid_hand_date(connection)
    if latest is None:
        return None, None
    if normalized in {"latest_valid_week", "current_week", "this_week", "week"}:
        start = latest - timedelta(days=latest.weekday())
        return start, start + timedelta(days=6)
    if normalized in {"latest_valid_day", "current_day", "this_day", "day"}:
        return latest, latest
    if normalized in {"latest_valid_month", "current_month", "this_month", "month"}:
        start = latest.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, next_month - timedelta(days=1)
    if ".." in normalized:
        left, right = normalized.split("..", 1)
        return parse_date(left), parse_date(right)
    parsed = parse_date(normalized)
    if parsed is not None:
        return parsed, parsed
    return latest - timedelta(days=latest.weekday()), latest


def latest_valid_hand_date(connection) -> date | None:
    row = connection.execute(
        """
        SELECT DATE(handtimestamp) AS hand_date
        FROM handhistories
        WHERE handtimestamp IS NOT NULL
          AND DATE(handtimestamp) != '1970-01-01'
        ORDER BY handtimestamp DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None or row["hand_date"] is None:
        return None
    return parse_date(str(row["hand_date"]))


def parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def aggregate_hand_period(
    connection,
    hero_name: str,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    aliases = [alias.lower() for alias in hero_aliases_for_sql(hero_name)]
    hero_conditions = " OR ".join(["lower(handhistory) LIKE ?"] * len(aliases))
    hero_parameters = [f"%{alias}%" for alias in aliases]
    base_parameters = [start_date.isoformat(), end_date.isoformat()]
    row = connection.execute(
        f"""
        SELECT
          COUNT(*) AS total_hands,
          SUM(CASE WHEN lower(handhistory) LIKE '%all-in%'
                    OR lower(handhistory) LIKE '%all in%' THEN 1 ELSE 0 END) AS all_in_hands,
          SUM(CASE WHEN lower(handhistory) LIKE '%total pot%' THEN 1 ELSE 0 END) AS total_pot_rows,
          SUM(CASE WHEN {hero_conditions} THEN 1 ELSE 0 END) AS hero_text_hands,
          COUNT(DISTINCT tournament_number) AS tournaments
        FROM handhistories
        WHERE handtimestamp IS NOT NULL
          AND DATE(handtimestamp) BETWEEN ? AND ?
          AND DATE(handtimestamp) != '1970-01-01'
        """,
        [*hero_parameters, *base_parameters],
    ).fetchone()
    return {
        "total_hands": int(row["total_hands"] or 0),
        "all_in_hands": int(row["all_in_hands"] or 0),
        "total_pot_rows": int(row["total_pot_rows"] or 0),
        "hero_text_hands": int(row["hero_text_hands"] or 0),
        "tournaments": int(row["tournaments"] or 0),
        "date_from": start_date.isoformat(),
        "date_to": end_date.isoformat(),
    }


def hero_aliases_for_sql(hero_name: str) -> list[str]:
    aliases = [hero_name.strip(), "hero"]
    result = []
    seen = set()
    for alias in aliases:
        lowered = alias.lower()
        if alias and lowered not in seen:
            result.append(alias)
            seen.add(lowered)
    return result


def get_candidate_hands_for_leak(
    settings: Settings,
    leak_key: str,
    period: str | None = None,
    limit: int = DEEP_HAND_LIMIT,
) -> dict[str, Any]:
    database_path = settings.hm3_db_path
    if database_path is None:
        warning = missing_database_path_warning()
        return {"connected": False, "hands": [], "warnings": [warning]}
    with connect_readonly(database_path) as connection:
        tables = set(list_tables(connection))
        if "handhistories" not in tables:
            return {"connected": True, "hands": [], "warnings": ["handhistories table is missing."]}
        rows = select_candidate_rows(connection, leak_key, period, min(limit * 25, 5000))
        analyzed = [analyze_hand_row(row, settings.hero_name) for row in rows]
    ranked = rank_hands_for_leak(analyzed, leak_key)
    return {
        "connected": True,
        "leak_key": leak_key,
        "period": normalize_period(period),
        "hands": [hand_summary_for_report(hand) for hand in ranked[:limit]],
        "sample_size": len(rows),
        "warnings": [],
    }


def get_hand_details_batch(
    settings: Settings,
    hand_ids: list[int],
    limit: int = 10,
) -> dict[str, Any]:
    database_path = settings.hm3_db_path
    if database_path is None:
        warning = missing_database_path_warning()
        return {"connected": False, "hands": [], "warnings": [warning]}
    bounded_ids = [int(hand_id) for hand_id in hand_ids[: min(limit, DEEP_HAND_LIMIT)]]
    with connect_readonly(database_path) as connection:
        details = [
            get_connected_hand_detail(connection, hand_id).model_dump() for hand_id in bounded_ids
        ]
    return {"connected": True, "hands": details, "warnings": []}


def analyze_hand_actions_batch(
    settings: Settings,
    hand_ids: list[int],
    limit: int = 10,
) -> dict[str, Any]:
    details = get_hand_details_batch(settings, hand_ids, limit)
    analyses = []
    for hand in details.get("hands", []):
        hand_text = str(hand.get("hand_text") or "")
        parsed = parse_hand_text(hand_text, settings.hero_name)
        analyses.append(
            {
                "hand_id": hand.get("hand_id"),
                "tournament_number": hand.get("tournament_number"),
                "hand_date": hand.get("hand_date"),
                "hero_position": parsed.get("hero_position"),
                "hero_stack_bb": parsed.get("hero_stack_bb"),
                "hero_cards_seen": parsed.get("hero_cards_seen"),
                "hero_actions": parsed.get("hero_actions", []),
                "pot_size": extract_pot_from_text(hand_text),
                "coach_questions": hand_review_questions(parsed.get("hero_actions", [])),
                "hand_text_excerpt": excerpt_hand_text(hand_text),
            }
        )
    return {
        "connected": details.get("connected", False),
        "hands": analyses,
        "warnings": details.get("warnings", []),
    }


def build_stat_leaks(stats: dict[str, Any], raw_counts: dict[str, Any]) -> list[TrainingLeak]:
    leaks: list[TrainingLeak] = []
    total_hands = int(stats.get("total_hands") or 0)
    gap = stats.get("vpip_pfr_gap_pct")
    if gap is not None and gap >= 5:
        leaks.append(
            TrainingLeak(
                leak_key="passive_preflop_gap",
                title="Passive preflop gap",
                severity="high" if gap < 7 else "critical",
                evidence=f"VPIP/PFR gap is {gap}% over {total_hands} hands.",
                coach_read=(
                    "Look for flats, limp-calls, and missed iso raises. "
                    "At microstakes, weak entries should often be attacked."
                ),
                sample_size=total_hands,
                confidence="high" if total_hands >= 5000 else "medium",
            )
        )
    fold_to_3bet = stats.get("fold_to_3bet_pct")
    faced_3bet = int(raw_counts.get("facedthreebetpreflop") or 0)
    if fold_to_3bet is not None and faced_3bet >= 100:
        if fold_to_3bet < 55:
            leaks.append(
                TrainingLeak(
                    leak_key="sticky_vs_3bet",
                    title="Sticky versus 3bets",
                    severity="high",
                    evidence=f"Fold to 3Bet is {fold_to_3bet}% over {faced_3bet} spots.",
                    coach_read=(
                        "Microstakes 3bets are often value-heavy. Review OOP calls and broadways."
                    ),
                    sample_size=faced_3bet,
                    confidence="medium",
                )
            )
        elif fold_to_3bet > 68:
            leaks.append(
                TrainingLeak(
                    leak_key="overfold_vs_3bet",
                    title="Possible overfold versus 3bets",
                    severity="medium",
                    evidence=f"Fold to 3Bet is {fold_to_3bet}% over {faced_3bet} spots.",
                    coach_read=(
                        "Check if late-position opens are folding too much to active restealers."
                    ),
                    sample_size=faced_3bet,
                    confidence="medium",
                )
            )
    wtsd = stats.get("wtsd_pct")
    wssd = stats.get("wssd_pct")
    sawflop = int(raw_counts.get("sawflop") or 0)
    if wtsd is not None and sawflop >= 500 and wtsd >= 36:
        leaks.append(
            TrainingLeak(
                leak_key="showdown_discipline",
                title="Showdown discipline",
                severity="medium" if wssd and wssd >= 50 else "high",
                evidence=f"WTSD {wtsd}% and W$SD {wssd}% over {sawflop} saw-flop hands.",
                coach_read=(
                    "Review river calls and medium-strength hands versus passive aggression."
                ),
                sample_size=sawflop,
                confidence="medium",
            )
        )
    cbet = stats.get("flop_cbet_pct")
    cbet_spots = int(raw_counts.get("flopcontinuationbetpossible") or 0)
    if cbet is not None and cbet_spots >= 500:
        if cbet < 55:
            leaks.append(
                TrainingLeak(
                    leak_key="missed_flop_cbet",
                    title="Missed small cbet spots",
                    severity="medium",
                    evidence=f"Flop CBet is {cbet}% over {cbet_spots} spots.",
                    coach_read="Find dry boards versus BB where a cheap 25-33% cbet prints folds.",
                    sample_size=cbet_spots,
                    confidence="medium",
                )
            )
        elif cbet > 72:
            leaks.append(
                TrainingLeak(
                    leak_key="over_cbet",
                    title="Possible over-cbet",
                    severity="medium",
                    evidence=f"Flop CBet is {cbet}% over {cbet_spots} spots.",
                    coach_read="Check wet boards and multiway pots where cbetting air loses EV.",
                    sample_size=cbet_spots,
                    confidence="medium",
                )
            )
    aggression = stats.get("aggression_factor_estimate")
    if aggression is not None and total_hands >= 1000:
        if aggression < 2:
            leaks.append(
                TrainingLeak(
                    leak_key="postflop_passivity",
                    title="Postflop passivity",
                    severity="medium",
                    evidence=f"Aggression factor estimate is {aggression}.",
                    coach_read=(
                        "Check value bets versus stations and probes when ranges are capped."
                    ),
                    sample_size=total_hands,
                    confidence="low",
                )
            )
        elif aggression > 4:
            leaks.append(
                TrainingLeak(
                    leak_key="postflop_spew",
                    title="Possible postflop spew",
                    severity="medium",
                    evidence=f"Aggression factor estimate is {aggression}.",
                    coach_read="Check if aggression targets weakness or fires into strong ranges.",
                    sample_size=total_hands,
                    confidence="low",
                )
            )
    leaks.append(
        TrainingLeak(
            leak_key="large_pot_quality",
            title="Large pot decision quality",
            severity="high",
            evidence="Large pots and all-in hands have the biggest EV swing.",
            coach_read="Review value target, bluff target, fold equity, and call-off discipline.",
            sample_size=total_hands,
            confidence="medium",
        )
    )
    leaks.append(
        TrainingLeak(
            leak_key="tournament_cluster_risk",
            title="Tournament cluster risk",
            severity="medium",
            evidence="Clusters of many priority hands can reveal tilt or pressure mistakes.",
            coach_read="Review clustered tournaments as a story, not isolated hands.",
            sample_size=total_hands,
            confidence="medium",
        )
    )
    return sorted(leaks, key=severity_rank)[:10]


def study_items_from_leaks(leaks: list[TrainingLeak]) -> list[TrainingStudyItem]:
    items = []
    for leak in leaks[:3]:
        items.append(
            TrainingStudyItem(
                title=leak.title,
                drill=f"Review {min(len(leak.related_hand_ids), 8)} hands for {leak.title}.",
                checklist=[
                    "Write effective stack in bb.",
                    "Mark position and preflop line.",
                    "Choose value target or bluff target.",
                    "State the exploit for next session.",
                ],
                linked_leak_keys=[leak.leak_key],
                linked_hand_ids=leak.related_hand_ids[:8],
            )
        )
    return items


def aggregate_player_month(
    connection,
    player_id: int,
    period: str | None,
) -> dict[str, float]:
    if period is None:
        return {column: 0.0 for column in MONTHLY_REQUIRED_COLUMNS if column != "player_id"}
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
        WHERE player_id = ? AND playedyearandmonth = ?
        """,
        (player_id, int(period)),
    ).fetchone()
    return {key: float(row[key] or 0) for key in row.keys()}


def select_candidate_rows(connection, leak_key: str, period: str | None, limit: int):
    period_prefix = period_to_date_prefix(period)
    where = [
        "handhistory IS NOT NULL",
        "TRIM(handhistory) != ''",
    ]
    parameters: list[Any] = []
    if period_prefix:
        where.append("handtimestamp LIKE ?")
        parameters.append(f"{period_prefix}%")
    lowered_key = leak_key.lower()
    if "3bet" in lowered_key:
        where.append("(lower(handhistory) LIKE '%3-bet%' OR lower(handhistory) LIKE '%3bet%')")
    elif "cbet" in lowered_key or "postflop" in lowered_key:
        where.append("(lower(handhistory) LIKE '%flop%' OR lower(handhistory) LIKE '%turn%')")
    elif "passive" in lowered_key:
        where.append("(lower(handhistory) LIKE '% calls %' OR lower(handhistory) LIKE '% limps %')")
    else:
        where.append(
            "(lower(handhistory) LIKE '%all-in%' OR lower(handhistory) LIKE '%total pot%')"
        )
    return connection.execute(
        f"""
        SELECT handhistory_id, handhistory, handtimestamp, tournament_number
        FROM handhistories
        WHERE {" AND ".join(where)}
        ORDER BY handhistory_id DESC
        LIMIT ?
        """,
        [*parameters, limit],
    ).fetchall()


def rank_hands_for_leak(hands: list[dict[str, Any]], leak_key: str) -> list[dict[str, Any]]:
    return sorted(hands, key=lambda hand: hand_score_for_leak(hand, leak_key), reverse=True)


def hand_score_for_leak(hand: dict[str, Any], leak_key: str) -> tuple[int, int]:
    score = 0
    actions = set(hand.get("hero_actions", []))
    if hand.get("has_hero"):
        score += 20
    if "call" in actions or "all-in call" in actions:
        score += 20
    if hand.get("is_all_in"):
        score += 20
    if hand.get("large_pot"):
        score += 20
    if hand.get("hero_position") in {"CO", "BTN", "SB", "BB"}:
        score += 10
    if "passive" in leak_key and "call" in actions:
        score += 20
    if "3bet" in leak_key and ("call" in actions or "all-in call" in actions):
        score += 20
    return score, int(hand.get("hand_id") or 0)


def severity_rank(leak: TrainingLeak) -> tuple[int, str]:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return order.get(leak.severity, 9), leak.leak_key


def normalize_period(period: str | None) -> str | None:
    if not period:
        return None
    digits = "".join(character for character in str(period) if character.isdigit())
    if len(digits) >= 6:
        return digits[:6]
    return None


def latest_period(trend: list[dict[str, Any]]) -> str | None:
    periods = [str(row["period"]) for row in trend if row.get("period")]
    return max(periods) if periods else None


def period_to_date_prefix(period: str | None) -> str | None:
    normalized = normalize_period(period)
    if normalized is None:
        return None
    return f"{normalized[:4]}-{normalized[4:6]}"


def extract_pot_from_text(hand_text: str) -> int | None:
    from poker_ai_coach.reports.hand_review_queue import parse_large_pot

    return parse_large_pot(hand_text)


def hand_review_questions(actions: list[str]) -> list[str]:
    questions = ["What was the value target or bluff target?"]
    if "call" in actions or "all-in call" in actions:
        questions.append("Was call better than raise or fold?")
    if "all-in shove" in actions or "all-in" in actions:
        questions.append("Did hero have fold equity?")
    questions.append("What exploit should hero use next time?")
    return questions


def excerpt_hand_text(hand_text: str) -> str:
    lines = [line.strip() for line in hand_text.splitlines() if line.strip()]
    useful = [
        line
        for line in lines
        if any(
            marker in line.lower()
            for marker in ["dealt to", "hero", "all-in", "calls", "raises", "bets", "total pot"]
        )
    ]
    return " | ".join((useful or lines)[:10])[:1200]
