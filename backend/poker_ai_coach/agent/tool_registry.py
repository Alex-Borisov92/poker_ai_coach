import json
from pathlib import Path
from typing import Any

from poker_ai_coach.agent.db_description import DB_DESCRIPTION, UNSUPPORTED_STATS
from poker_ai_coach.coach.principles import load_coaching_principles
from poker_ai_coach.config import Settings
from poker_ai_coach.db.hm3_connection import connect_readonly
from poker_ai_coach.db.schema_overview import (
    STAT_MAPPINGS,
    build_schema_overview,
    create_explorer_snapshot,
)
from poker_ai_coach.db.schema_probe import EXPECTED_TABLES, count_table_rows, list_tables
from poker_ai_coach.reports.coach_scout import build_coach_scout_report
from poker_ai_coach.reports.deep_leaks import (
    analyze_hand_actions_batch,
    find_stat_leaks,
    get_candidate_hands_for_leak,
    get_hand_details_batch,
    get_monthly_hm3_stats,
)
from poker_ai_coach.reports.hand_review_queue import (
    get_hand_detail,
    has_all_in_text,
    normalize_date,
    parse_large_pot,
    table_columns,
)
from poker_ai_coach.reports.hero_aliases import hero_aliases, text_has_hero_alias
from poker_ai_coach.reports.hm3_player_stats import build_hm3_player_stats
from poker_ai_coach.reports.leak_finder import build_leak_finder_report
from poker_ai_coach.reports.overview import get_date_coverage
from poker_ai_coach.reports.study_plan import build_study_plan

MAX_TOOL_LIMIT = 50
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
KNOWLEDGE_TOPICS = {
    "schema": "HM3_SCHEMA_GUIDE.md",
    "stats": "HM3_STAT_MAPPINGS.md",
    "micro_mtt": "MICRO_MTT_STAT_COACHING.md",
    "leak_finder": "LEAK_FINDER_PROTOCOL.md",
    "study_plan": "STUDY_PLAN_PROTOCOL.md",
    "safety": "DB_SAFETY_RULES.md",
}


def tool_definitions() -> list[dict[str, Any]]:
    return [
        function_tool(
            "get_database_profile",
            "Return safe HM3 database profile, basename only, schema status, counts, and caveats.",
            {},
        ),
        function_tool(
            "get_hm3_schema_overview",
            "Return safe HM3 schema overview with tables, columns, relationships, and caveats.",
            {},
        ),
        function_tool(
            "get_hm3_stat_mappings",
            "Return supported HM3 stat formulas and confidence levels.",
            {},
        ),
        function_tool(
            "get_hm3_player_stats",
            (
                "Return HM3 aggregate player stats like VPIP, PFR, 3Bet, "
                "bb/100, WTSD, W$SD, and trends."
            ),
            {},
        ),
        function_tool(
            "get_monthly_hm3_stats",
            "Return HM3 aggregate stats for a monthly period or latest available period.",
            {"period": {"type": "string"}},
        ),
        function_tool(
            "find_stat_leaks",
            "Return structured leak candidates with severity from supported HM3 stats.",
            {
                "period": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
        ),
        function_tool(
            "get_candidate_hands_for_leak",
            "Return hand summaries that can illustrate one supported leak candidate.",
            {
                "leak_key": {"type": "string"},
                "period": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            required=["leak_key"],
        ),
        function_tool(
            "get_hand_details_batch",
            "Return full text for selected historical hand IDs, capped at 10 hands.",
            {
                "hand_ids": {"type": "array", "items": {"type": "integer"}, "maxItems": 10},
            },
            required=["hand_ids"],
        ),
        function_tool(
            "analyze_hand_actions_batch",
            "Parse selected historical hands into coach-friendly action summaries.",
            {
                "hand_ids": {"type": "array", "items": {"type": "integer"}, "maxItems": 10},
            },
            required=["hand_ids"],
        ),
        function_tool(
            "get_coach_scout_report",
            "Return deterministic coach scout report with action patterns, clusters, and hand IDs.",
            {},
        ),
        function_tool(
            "search_hands",
            "Search historical hands by safe filters. Returns summaries only, no full hand text.",
            {
                "all_in": {"type": "boolean"},
                "large_pot": {"type": "boolean"},
                "tournament_number": {"type": "string"},
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT},
            },
        ),
        function_tool(
            "get_hand_detail",
            "Return one selected historical hand text by hand ID.",
            {"hand_id": {"type": "integer", "minimum": 1}},
            required=["hand_id"],
        ),
        function_tool(
            "get_tournament_story",
            "Return key hands and timeline for one tournament number.",
            {
                "tournament_number": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT},
            },
            required=["tournament_number"],
        ),
        function_tool(
            "get_player_action_patterns",
            "Return hero action counts, stack bands, positions, and selected insights.",
            {},
        ),
        function_tool(
            "get_agent_knowledge",
            "Return bounded local agent knowledge for one topic.",
            {"topic": {"type": "string", "enum": sorted(KNOWLEDGE_TOPICS)}},
            required=["topic"],
        ),
        function_tool(
            "create_explorer_snapshot",
            "Create sanitized local SQLite schema snapshot for DBeaver.",
            {},
        ),
        function_tool(
            "get_leak_finder_context",
            "Return deterministic fallback leak context plus HM3 stats for AI leak analysis.",
            {},
        ),
        function_tool(
            "get_study_plan_context",
            "Return deterministic fallback study context plus HM3 stats for AI plan generation.",
            {},
        ),
        function_tool(
            "get_coaching_principles",
            "Return local coaching doctrine from COACHING_PRINCIPLES.MD.",
            {},
        ),
        function_tool(
            "create_study_drill",
            "Create a deterministic drill from selected hand IDs and focus area.",
            {
                "hand_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "maxItems": 10,
                },
                "focus": {"type": "string"},
            },
        ),
    ]


def function_tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        },
    }


def execute_tool(settings: Settings, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "get_database_profile":
        return get_database_profile(settings)
    if name == "get_hm3_schema_overview":
        return build_schema_overview(settings)
    if name == "get_hm3_stat_mappings":
        return {"stat_mappings": STAT_MAPPINGS}
    if name == "get_hm3_player_stats":
        return build_hm3_player_stats(settings)
    if name == "get_monthly_hm3_stats":
        return get_monthly_hm3_stats(settings, arguments.get("period"))
    if name == "find_stat_leaks":
        return find_stat_leaks(
            settings,
            arguments.get("period"),
            int(arguments.get("limit") or 10),
        )
    if name == "get_candidate_hands_for_leak":
        return get_candidate_hands_for_leak(
            settings,
            str(arguments["leak_key"]),
            arguments.get("period"),
            int(arguments.get("limit") or 10),
        )
    if name == "get_hand_details_batch":
        return get_hand_details_batch(
            settings,
            [int(hand_id) for hand_id in arguments.get("hand_ids", [])],
            10,
        )
    if name == "analyze_hand_actions_batch":
        return analyze_hand_actions_batch(
            settings,
            [int(hand_id) for hand_id in arguments.get("hand_ids", [])],
            10,
        )
    if name == "get_coach_scout_report":
        return build_coach_scout_report(settings)
    if name == "search_hands":
        return search_hands(settings, arguments)
    if name == "get_hand_detail":
        return get_hand_detail(settings, int(arguments["hand_id"])).model_dump()
    if name == "get_tournament_story":
        return get_tournament_story(settings, arguments)
    if name == "get_player_action_patterns":
        return get_player_action_patterns(settings)
    if name == "get_agent_knowledge":
        return get_agent_knowledge(str(arguments["topic"]))
    if name == "create_explorer_snapshot":
        return create_explorer_snapshot(settings)
    if name == "get_leak_finder_context":
        return get_leak_finder_context(settings)
    if name == "get_study_plan_context":
        return get_study_plan_context(settings)
    if name == "get_coaching_principles":
        return {"principles": load_coaching_principles()}
    if name == "create_study_drill":
        return create_study_drill(arguments)
    return {"error": f"Unknown tool: {name}"}


def tool_output_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def get_database_profile(settings: Settings) -> dict[str, Any]:
    database_path = settings.hm3_db_path
    if database_path is None:
        return {
            "configured": False,
            "connected": False,
            "hero_name": settings.hero_name,
            "hero_aliases": hero_aliases(settings.hero_name),
            "warnings": ["HM3_DB_PATH is not configured."],
        }
    with connect_readonly(database_path) as connection:
        tables = set(list_tables(connection))
        counts = {
            table: count_table_rows(connection, table)
            for table in EXPECTED_TABLES
            if table in tables
        }
        date_range, valid_dates, invalid_dates, date_warnings = get_date_coverage(
            connection, tables
        )
        return {
            "configured": True,
            "connected": True,
            "database_name": database_path.name,
            "hero_name": settings.hero_name,
            "hero_aliases": hero_aliases(settings.hero_name),
            "tables_found": sorted(tables),
            "expected_tables": EXPECTED_TABLES,
            "missing_tables": [table for table in EXPECTED_TABLES if table not in tables],
            "table_counts": counts,
            "date_range": date_range.model_dump(),
            "valid_date_count": valid_dates,
            "invalid_1970_date_count": invalid_dates,
            "warnings": date_warnings,
            "db_description": DB_DESCRIPTION,
            "unsupported_stats": UNSUPPORTED_STATS,
        }


def search_hands(settings: Settings, arguments: dict[str, Any]) -> dict[str, Any]:
    database_path = settings.hm3_db_path
    if database_path is None:
        return {"connected": False, "hands": [], "warnings": ["HM3_DB_PATH is not configured."]}
    limit = min(int(arguments.get("limit") or 20), MAX_TOOL_LIMIT)
    filters = {
        "all_in": bool(arguments.get("all_in", False)),
        "large_pot": bool(arguments.get("large_pot", False)),
        "tournament_number": str(arguments.get("tournament_number") or "").strip() or None,
        "date_from": str(arguments.get("date_from") or "").strip() or None,
        "date_to": str(arguments.get("date_to") or "").strip() or None,
    }
    with connect_readonly(database_path) as connection:
        tables = set(list_tables(connection))
        if "handhistories" not in tables:
            return {"connected": True, "hands": [], "warnings": ["handhistories table is missing."]}
        columns = table_columns(connection, "handhistories")
        required = {"handhistory_id", "handhistory", "handtimestamp", "tournament_number"}
        missing = sorted(required - columns)
        if missing:
            return {"connected": True, "hands": [], "warnings": [f"Missing columns: {missing}"]}
        rows = connection.execute(
            """
            SELECT handhistory_id, handhistory, handtimestamp, tournament_number
            FROM handhistories
            WHERE handhistory IS NOT NULL
              AND TRIM(handhistory) != ''
            ORDER BY handhistory_id DESC
            LIMIT 5000
            """
        ).fetchall()
    hands = []
    for row in rows:
        text = str(row["handhistory"] or "")
        hand_date, is_unknown = normalize_date(row["handtimestamp"])
        pot_size = parse_large_pot(text)
        if filters["all_in"] and not has_all_in_text(text):
            continue
        if filters["large_pot"] and pot_size is None:
            continue
        if (
            filters["tournament_number"]
            and str(row["tournament_number"]) != filters["tournament_number"]
        ):
            continue
        if filters["date_from"] and (hand_date is None or hand_date < filters["date_from"]):
            continue
        if filters["date_to"] and (hand_date is None or hand_date > filters["date_to"]):
            continue
        hands.append(
            {
                "hand_id": int(row["handhistory_id"]),
                "tournament_number": (
                    str(row["tournament_number"]) if row["tournament_number"] is not None else None
                ),
                "hand_date": hand_date,
                "is_date_unknown": is_unknown,
                "has_hero": text_has_hero_alias(text, settings.hero_name),
                "is_all_in": has_all_in_text(text),
                "pot_size": pot_size,
                "summary": summarize_hand_text(text),
            }
        )
        if len(hands) >= limit:
            break
    return {
        "connected": True,
        "filters": filters,
        "sample_size": len(rows),
        "hands": hands,
        "confidence": "medium" if hands else "low",
        "missing_data": [],
    }


def get_tournament_story(settings: Settings, arguments: dict[str, Any]) -> dict[str, Any]:
    tournament_number = str(arguments["tournament_number"])
    result = search_hands(
        settings,
        {"tournament_number": tournament_number, "limit": arguments.get("limit", 30)},
    )
    hands = result.get("hands", [])
    all_in_count = sum(1 for hand in hands if hand.get("is_all_in"))
    large_pot_count = sum(1 for hand in hands if hand.get("pot_size"))
    return {
        "tournament_number": tournament_number,
        "sample_size": len(hands),
        "all_in_count": all_in_count,
        "large_pot_count": large_pot_count,
        "hands": hands,
        "coach_angle": (
            "Review this tournament as a story: stack swings, all-ins, large pots, "
            "pressure points, and possible tilt."
        ),
        "confidence": "medium" if len(hands) >= 5 else "low",
    }


def get_player_action_patterns(settings: Settings) -> dict[str, Any]:
    scout = build_coach_scout_report(settings)
    return {
        "sample_size": scout.get("hero_text_hands", 0),
        "hero_action_counts": scout.get("hero_action_counts", {}),
        "hero_position_counts": scout.get("hero_position_counts", {}),
        "hero_stack_bands": scout.get("hero_stack_bands", {}),
        "insights": scout.get("insights", []),
        "confidence": "medium",
        "missing_data": scout.get("missing_data", []),
    }


def get_agent_knowledge(topic: str) -> dict[str, Any]:
    filename = KNOWLEDGE_TOPICS.get(topic)
    if filename is None:
        return {"topic": topic, "content": "", "warnings": ["Unknown knowledge topic."]}
    path = KNOWLEDGE_DIR / filename
    return {
        "topic": topic,
        "filename": filename,
        "content": path.read_text(encoding="utf-8")[:12000],
    }


def get_leak_finder_context(settings: Settings) -> dict[str, Any]:
    return {
        "hm3_player_stats": build_hm3_player_stats(settings),
        "deterministic_leak_report": build_leak_finder_report(settings).model_dump(),
        "knowledge": get_agent_knowledge("leak_finder"),
        "coach_instruction": (
            "Generate the final leak report as a coach. Use deterministic data as context, "
            "not as the final UI copy."
        ),
    }


def get_study_plan_context(settings: Settings) -> dict[str, Any]:
    return {
        "hm3_player_stats": build_hm3_player_stats(settings),
        "deterministic_study_plan": build_study_plan(settings).model_dump(),
        "knowledge": get_agent_knowledge("study_plan"),
        "coach_instruction": (
            "Generate a practical weekly plan from stats, leak hypotheses, and selected hands."
        ),
    }


def create_study_drill(arguments: dict[str, Any]) -> dict[str, Any]:
    hand_ids = [int(hand_id) for hand_id in arguments.get("hand_ids", [])][:10]
    focus = str(arguments.get("focus") or "selected hands")
    checklist = [
        "Write effective stack in bb.",
        "Mark position and preflop action.",
        "Choose value target and bluff target.",
        "Estimate fold equity.",
        "Write one exploitative adjustment for the next session.",
    ]
    return {
        "focus": focus,
        "hand_ids": hand_ids,
        "drill": f"Review {len(hand_ids)} hands for {focus}.",
        "checklist": checklist,
        "confidence": "high" if hand_ids else "low",
    }


def summarize_hand_text(text: str) -> str:
    useful_lines = []
    for line in text.splitlines():
        lowered = line.lower()
        if (
            "hero" in lowered
            or "all-in" in lowered
            or "all in" in lowered
            or "total pot" in lowered
            or "dealt to" in lowered
        ):
            useful_lines.append(line.strip())
        if len(useful_lines) >= 6:
            break
    return " | ".join(useful_lines)[:700]
