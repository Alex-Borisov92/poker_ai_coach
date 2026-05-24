import json
import uuid
from typing import Any, Protocol

import httpx

from poker_ai_coach.agent.tool_registry import execute_tool, tool_definitions, tool_output_json
from poker_ai_coach.coach.prompts import SYSTEM_PROMPT
from poker_ai_coach.coach.service import MISSING_API_KEY_WARNING, ai_configured
from poker_ai_coach.config import Settings
from poker_ai_coach.models.coach import AgentChatRequest, AgentChatResponse, AgentToolStep

MAX_TOOL_STEPS = 20
_SESSION_RESPONSES: dict[str, str] = {}
CONTROLLED_MODES = {
    "database_scout",
    "stats_overview",
    "leak_finder",
    "study_plan",
    "tournament_story",
    "training_initial",
    "training_followup",
    "leak_finder_deep",
    "study_plan_deep",
    "hand_batch_review",
}


class ResponsesTransport(Protocol):
    def create_response(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class HttpxResponsesTransport:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def create_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=240.0,
        )
        response.raise_for_status()
        return response.json()


def run_agent_chat(
    settings: Settings,
    request: AgentChatRequest,
    transport: ResponsesTransport | None = None,
) -> AgentChatResponse:
    session_id = request.session_id or str(uuid.uuid4())
    model = settings.openai_model or "gpt-5-mini"
    if not ai_configured(settings):
        warnings = []
        if not settings.ai_enabled:
            warnings.append("AI_ENABLED is false.")
        if settings.ai_enabled and not settings.openai_api_key:
            warnings.append(MISSING_API_KEY_WARNING)
        return AgentChatResponse(
            ai_enabled=settings.ai_enabled,
            ai_configured=False,
            provider="mock",
            model=model,
            session_id=session_id,
            content=(
                "AI coach is disabled or missing configuration. No data was sent to an AI provider."
            ),
            warnings=warnings,
        )

    selected_transport = transport or HttpxResponsesTransport(str(settings.openai_api_key))
    if should_use_controlled_context(request):
        return run_controlled_agent(settings, request, selected_transport, session_id, model)

    input_items: list[dict[str, Any]] = [
        {"role": "user", "content": request.message},
    ]
    previous_response_id = _SESSION_RESPONSES.get(session_id)
    tool_steps: list[AgentToolStep] = []
    selected_hand_ids: list[int] = []
    final_response: dict[str, Any] | None = None

    for _ in range(MAX_TOOL_STEPS):
        payload: dict[str, Any] = {
            "model": model,
            "instructions": agent_instructions(request.mode),
            "tools": tool_definitions(),
            "input": input_items,
            "parallel_tool_calls": False,
            "store": True,
        }
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id
        response = selected_transport.create_response(payload)
        final_response = response
        tool_calls = function_calls_from_response(response)
        if not tool_calls:
            break

        input_items = output_items_for_next_request(response)
        for call in tool_calls:
            name = str(call.get("name") or "")
            call_id = str(call.get("call_id") or call.get("id") or "")
            arguments = parse_arguments(call.get("arguments"))
            output = execute_tool(settings, name, arguments)
            selected_hand_ids.extend(extract_hand_ids(output))
            tool_steps.append(
                AgentToolStep(
                    name=name,
                    arguments=arguments,
                    summary=summarize_tool_output(name, output),
                )
            )
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": tool_output_json(output),
                }
            )
    else:
        final_response = request_final_answer(
            selected_transport,
            model,
            agent_instructions(request.mode),
            input_items,
            previous_response_id,
        )
        warnings = [
            "Maximum tool step limit reached. "
            "The agent wrote a final answer from collected evidence."
        ]
        if final_response and final_response.get("id"):
            _SESSION_RESPONSES[session_id] = str(final_response["id"])
        return AgentChatResponse(
            ai_enabled=True,
            ai_configured=True,
            provider="openai",
            model=model,
            session_id=session_id,
            content=extract_output_text(final_response or {}),
            tool_steps=tool_steps,
            selected_hand_ids=unique_ids(selected_hand_ids),
            warnings=warnings,
        )

    if final_response and final_response.get("id"):
        _SESSION_RESPONSES[session_id] = str(final_response["id"])

    return AgentChatResponse(
        ai_enabled=True,
        ai_configured=True,
        provider="openai",
        model=model,
        session_id=session_id,
        content=extract_output_text(final_response or {}),
        tool_steps=tool_steps,
        selected_hand_ids=unique_ids(selected_hand_ids),
    )


def run_controlled_agent(
    settings: Settings,
    request: AgentChatRequest,
    transport: ResponsesTransport,
    session_id: str,
    model: str,
) -> AgentChatResponse:
    tool_plan = controlled_tool_plan(request)
    tool_steps: list[AgentToolStep] = []
    tool_outputs: dict[str, Any] = {}
    selected_hand_ids: list[int] = []

    for name, arguments in tool_plan:
        output = execute_tool(settings, name, arguments)
        tool_outputs[name] = output
        selected_hand_ids.extend(extract_hand_ids(output))
        tool_steps.append(
            AgentToolStep(
                name=name,
                arguments=arguments,
                summary=summarize_tool_output(name, output),
            )
        )

    drill_hand_ids = unique_ids(selected_hand_ids)[:8]
    if drill_hand_ids:
        drill_output = execute_tool(
            settings,
            "create_study_drill",
            {"hand_ids": drill_hand_ids, "focus": f"{request.mode} review hands"},
        )
        tool_outputs["create_study_drill"] = drill_output
        selected_hand_ids.extend(extract_hand_ids(drill_output))
        tool_steps.append(
            AgentToolStep(
                name="create_study_drill",
                arguments={"hand_ids": drill_hand_ids, "focus": f"{request.mode} review hands"},
                summary=summarize_tool_output("create_study_drill", drill_output),
            )
        )

    try:
        final_response = transport.create_response(
            {
                "model": model,
                "instructions": controlled_agent_instructions(request.mode),
                "input": [
                    {"role": "user", "content": request.message},
                    {
                        "role": "user",
                        "content": (
                            f"Important: this is a {request.mode} request. "
                            "Use the provided local tool outputs. Do not ask for more tools."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Safe local tool outputs JSON. Use only this evidence.\n"
                            f"{tool_output_json(tool_outputs)}"
                        ),
                    },
                ],
                "store": True,
            }
        )
    except httpx.HTTPError as exc:
        return AgentChatResponse(
            ai_enabled=True,
            ai_configured=True,
            provider="openai",
            model=model,
            session_id=session_id,
            content="Coach request failed before a final answer was returned.",
            tool_steps=tool_steps,
            selected_hand_ids=drill_hand_ids,
            warnings=[f"OpenAI request failed: {exc.__class__.__name__}."],
            error="Coach provider request failed.",
        )
    if final_response.get("id"):
        _SESSION_RESPONSES[session_id] = str(final_response["id"])

    return AgentChatResponse(
        ai_enabled=True,
        ai_configured=True,
        provider="openai",
        model=model,
        session_id=session_id,
        content=extract_output_text(final_response),
        tool_steps=tool_steps,
        selected_hand_ids=drill_hand_ids,
    )


def controlled_tool_plan(request: AgentChatRequest) -> list[tuple[str, dict[str, Any]]]:
    period_tools: list[tuple[str, dict[str, Any]]] = []
    if is_week_request(request.message):
        period_tools = [("get_hm3_period_stats", {"period": "latest_valid_week"})]
    if request.mode in {"leak_finder_deep", "training_initial", "training_followup"}:
        return [
            ("get_database_profile", {}),
            *period_tools,
            ("get_monthly_hm3_stats", {}),
            ("find_stat_leaks", {"limit": 10}),
            ("get_agent_knowledge", {"topic": "leak_finder"}),
            ("get_agent_knowledge", {"topic": "micro_mtt"}),
        ]
    if request.mode == "study_plan_deep":
        return [
            ("get_database_profile", {}),
            *period_tools,
            ("get_monthly_hm3_stats", {}),
            ("find_stat_leaks", {"limit": 10}),
            ("get_study_plan_context", {}),
            ("get_agent_knowledge", {"topic": "study_plan"}),
        ]
    if request.mode == "hand_batch_review":
        return [
            ("get_database_profile", {}),
            ("find_stat_leaks", {"limit": 5}),
        ]
    if request.mode == "leak_finder":
        return [
            ("get_database_profile", {}),
            *period_tools,
            ("get_hm3_player_stats", {}),
            ("get_hm3_stat_mappings", {}),
            ("get_agent_knowledge", {"topic": "leak_finder"}),
            ("get_agent_knowledge", {"topic": "micro_mtt"}),
            ("get_leak_finder_context", {}),
            ("get_coach_scout_report", {}),
            ("search_hands", {"all_in": True, "large_pot": True, "limit": 12}),
        ]
    if request.mode == "study_plan":
        return [
            ("get_database_profile", {}),
            ("get_hm3_player_stats", {}),
            ("get_agent_knowledge", {"topic": "study_plan"}),
            ("get_agent_knowledge", {"topic": "micro_mtt"}),
            ("get_study_plan_context", {}),
            ("get_coach_scout_report", {}),
            ("search_hands", {"all_in": True, "large_pot": True, "limit": 12}),
        ]
    if request.mode == "stats_overview":
        return [
            ("get_database_profile", {}),
            ("get_hm3_schema_overview", {}),
            *period_tools,
            ("get_hm3_player_stats", {}),
            ("get_hm3_stat_mappings", {}),
            ("get_agent_knowledge", {"topic": "stats"}),
            ("get_agent_knowledge", {"topic": "micro_mtt"}),
        ]
    if request.mode == "tournament_story":
        return [
            ("get_database_profile", {}),
            ("get_hm3_player_stats", {}),
            ("get_agent_knowledge", {"topic": "schema"}),
            ("get_coach_scout_report", {}),
        ]
    tool_plan: list[tuple[str, dict[str, Any]]] = [
        ("get_database_profile", {}),
        ("get_hm3_schema_overview", {}),
        *period_tools,
        ("get_hm3_player_stats", {}),
        ("get_hm3_stat_mappings", {}),
        ("get_coaching_principles", {}),
    ]
    if not is_stats_only_request(request.message):
        tool_plan.extend(
            [
                ("get_coach_scout_report", {}),
                ("search_hands", {"all_in": True, "large_pot": True, "limit": 12}),
            ]
        )
    return tool_plan


def request_final_answer(
    transport: ResponsesTransport,
    model: str,
    instructions: str,
    input_items: list[dict[str, Any]],
    previous_response_id: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "instructions": instructions,
        "input": [
            *input_items,
            {
                "role": "user",
                "content": (
                    "Tool budget is exhausted. Stop calling tools and write the final coach "
                    "answer now using only collected tool outputs."
                ),
            },
        ],
        "store": True,
    }
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    return transport.create_response(payload)


def agent_instructions(mode: str) -> str:
    return f"""
{SYSTEM_PROMPT}

You are now running as a local tool-using agent.
First explore with tools, then answer.
For stats or overview requests, call get_database_profile, get_hm3_player_stats,
get_hm3_schema_overview or get_hm3_stat_mappings before using hand text tools.
Use hand search only to verify hypotheses and pick concrete historical hands.
Prefer HM3 aggregate stats first: VPIP, PFR, 3Bet, bb/100, WTSD, W$SD, WWSF,
fold-to-3bet, cbet data, sample size, and trend data when available.
Never ask for arbitrary SQL. Never claim unsupported stats.
Safety contract:
- No raw SQL tool exists.
- Local tools must not write to the HM3 database.
- Never request full database upload.
- Request full hand text only for specific historical hand IDs.
Mode: {mode}.
Final answer sections:
Use Russian section titles. They should mean:
- Main takeaway
- What the stats say
- Coach read
- Hands to review
- Drill
- Confidence and limits
Style:
- Write like a coach, not like a database export.
- Start with the one main idea in 1-2 short sentences.
- Use short bullets. Each bullet should connect a stat to a poker meaning.
- Do not dump many numbers without explaining why they matter.
- Keep technical caveats in the last section unless they change the main conclusion.
- Use plain punctuation only. Do not use arrows or long dash characters.
""".strip()


def controlled_agent_instructions(mode: str) -> str:
    mode_focus = {
        "stats_overview": (
            "Build a coach overview from HM3 aggregate stats first. "
            "Do not make hand scan volume the main point."
        ),
        "leak_finder": (
            "Generate the Leak Finder as a coach. Use HM3 aggregate stats, leak protocol, "
            "and selected hand evidence. Deterministic reports are context, not final copy."
        ),
        "study_plan": (
            "Generate a weekly study plan from HM3 stats, leak hypotheses, selected hands, "
            "and coaching principles."
        ),
        "tournament_story": (
            "Explain tournament clusters as historical review material. "
            "Do not give live decision advice."
        ),
        "database_scout": (
            "Scout the database like a microstakes MTT coach and find useful insights."
        ),
        "training_initial": (
            "Create the first training input: stats, main leaks, concrete hands, and study focus."
        ),
        "training_followup": (
            "Compare this training with previous work and update open leaks and study plan."
        ),
        "leak_finder_deep": ("Find 5-10 leaks with severity and explain concrete hand examples."),
        "study_plan_deep": (
            "Create a practical plan from structured leaks and selected hand examples."
        ),
        "hand_batch_review": (
            "Review selected historical hands one by one and explain the action."
        ),
        "coach_overview": ("Build a practical coach overview from the provided database evidence."),
    }.get(mode, "Build a practical coach answer from the provided local evidence.")
    return f"""
{SYSTEM_PROMPT}

You are writing the final answer for a controlled local coach run.
The backend already ran safe local read-only tools.
Use only the provided JSON evidence.
Do not ask for more tools, SQL, screenshots, files, or database upload.
Mode focus: {mode_focus}
For overview and stats questions:
- If get_hm3_period_stats is present, use it as the primary source for the requested
  week/day/month window.
- Never present monthly aggregate VPIP/PFR/3Bet as exact weekly stats.
- The main insight must come from get_hm3_player_stats.stats, insights, or coach_priority.
- Discuss VPIP/PFR, 3Bet, bb/100, WTSD, W$SD, WWSF, fold-to-3bet, and cbet data first.
- Treat hand text scans as secondary evidence for selecting hands to review.
- Do not make all-in text volume the main insight unless the user explicitly asks about all-ins.
For Leak Finder and Study Plan:
- Start from HM3 aggregate stats and the local protocol files.
- Use selected hands as review targets, not as proof of population-wide leaks.
- Return concrete hand IDs only when they are present in tool outputs.
For deep leak requests:
- Return 5-10 leak candidates with severity: critical, high, medium, or low.
- For each important leak, include at least one concrete hand ID when available.
- Do not tell the user to manually find hands if hand IDs or hand details are available.
- Explain selected hands one by one: situation, hero action, likely decision point, coach note.
Mention database quality only as a caveat.
Answer in Russian.
Use this format:
Use Russian section titles, not English titles.

Section 1: Main takeaway
2 short sentences with the main coaching point.

Section 2: What the stats say
3-6 bullets. Each bullet: stat -> poker meaning.

Section 3: Coach read
Separate facts from hypotheses. Explain the likely leak in simple poker language.

Section 4: Hands to review
Concrete hand IDs when available and what to check in them.

Section 5: Drill
One practical drill for the next study block.

Section 6: Confidence and limits
Sample size, missing data, and caveats.

Style rules:
- Write like a coach talking to a player after a session.
- Make the main point easy to see.
- Prefer plain Russian. Use poker terms only when they add clarity.
- Do not write a dense stat dump.
- Do not hide important limits, but do not lead with database hygiene unless it is the main issue.
- Use plain punctuation only. Do not use arrows or long dash characters.
""".strip()


def should_use_controlled_context(request: AgentChatRequest) -> bool:
    if request.mode in CONTROLLED_MODES:
        return True
    if request.mode != "coach_overview":
        return False
    message = request.message.lower()
    scout_markers = [
        "overview",
        "scout",
        "database",
        "stats",
        "leak",
        "insight",
        "study plan",
        "\u043e\u0432\u0435\u0440",
        "\u043e\u0431\u0437\u043e\u0440",
        "\u0431\u0430\u0437",
        "\u0441\u0442\u0430\u0442",
        "\u043b\u0438\u043a",
        "\u0438\u043d\u0441\u0430\u0439\u0442",
        "\u043f\u043b\u0430\u043d",
        "\u043f\u0440\u043e\u0441\u0430\u0434",
    ]
    return any(marker in message for marker in scout_markers)


def is_stats_only_request(message: str) -> bool:
    lowered = message.lower()
    stats_markers = [
        "stats",
        "statistics",
        "stat report",
        "\u0441\u0442\u0430\u0442",
        "\u0441\u0442\u0430\u0442\u044b",
        "\u0441\u0442\u0430\u0442\u0430\u043c",
    ]
    hand_markers = [
        "hand",
        "hands",
        "\u0440\u0443\u043a",
        "\u0440\u0443\u043a\u0438",
        "\u0440\u0430\u0437\u0434\u0430\u0447",
        "all-in",
        "\u043e\u043b\u043b",
        "\u043e\u043b-\u0438\u043d",
    ]
    return any(marker in lowered for marker in stats_markers) and not any(
        marker in lowered for marker in hand_markers
    )


def is_week_request(message: str) -> bool:
    lowered = message.lower()
    markers = [
        "week",
        "weekly",
        "this week",
        "last week",
        "7 days",
        "недел",
        "эту неделю",
        "эта неделя",
        "последние 7",
    ]
    return any(marker in lowered for marker in markers)


def function_calls_from_response(response: dict[str, Any]) -> list[dict[str, Any]]:
    calls = []
    for item in response.get("output") or []:
        if item.get("type") in {"function_call", "function"}:
            calls.append(item)
    return calls


def output_items_for_next_request(response: dict[str, Any]) -> list[dict[str, Any]]:
    return list(response.get("output") or [])


def parse_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not raw_arguments:
        return {}
    try:
        value = json.loads(str(raw_arguments))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def extract_output_text(response: dict[str, Any]) -> str:
    if response.get("output_text"):
        return str(response["output_text"]).strip()
    chunks = []
    for item in response.get("output") or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if content.get("type") in {"output_text", "text"}:
                chunks.append(str(content.get("text") or ""))
    return "\n".join(chunks).strip()


def extract_hand_ids(value: Any) -> list[int]:
    ids: list[int] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "hand_id" and isinstance(item, int):
                ids.append(item)
            elif key == "hand_ids" and isinstance(item, list):
                ids.extend(int(hand_id) for hand_id in item if isinstance(hand_id, int))
            else:
                ids.extend(extract_hand_ids(item))
    elif isinstance(value, list):
        for item in value:
            ids.extend(extract_hand_ids(item))
    return ids


def unique_ids(values: list[int]) -> list[int]:
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result[:30]


def summarize_tool_output(name: str, output: dict[str, Any]) -> str:
    if name == "search_hands":
        return f"Found {len(output.get('hands', []))} hand summaries."
    if name == "get_hand_detail":
        return f"Loaded hand {output.get('hand_id')}."
    if name == "get_tournament_story":
        return (
            f"Checked tournament {output.get('tournament_number')} with "
            f"{output.get('sample_size', 0)} hands."
        )
    if name == "get_coach_scout_report":
        return (
            f"Scouted {output.get('scanned_hands', 0)} hands and "
            f"{len(output.get('insights', []))} insights."
        )
    if name == "get_hm3_player_stats":
        stats = output.get("stats", {})
        return (
            f"Loaded HM3 stats over {stats.get('total_hands', 0)} hands "
            f"with bb/100 {stats.get('bb100')}."
        )
    if name == "get_monthly_hm3_stats":
        stats = output.get("stats", {})
        return (
            f"Loaded monthly stats for {output.get('period') or 'unknown'} "
            f"over {stats.get('total_hands', 0)} hands."
        )
    if name == "get_hm3_period_stats":
        stats = output.get("stats", {})
        return (
            f"Loaded period stats for {output.get('date_from')}..{output.get('date_to')} "
            f"over {stats.get('total_hands', 0)} hands."
        )
    if name == "find_stat_leaks":
        return f"Found {len(output.get('leaks', []))} structured leak candidates."
    if name == "get_candidate_hands_for_leak":
        return f"Found {len(output.get('hands', []))} candidate hand examples."
    if name == "get_hand_details_batch":
        return f"Loaded {len(output.get('hands', []))} hand details."
    if name == "analyze_hand_actions_batch":
        return f"Parsed {len(output.get('hands', []))} selected hands."
    if name == "get_database_profile":
        return f"Checked database {output.get('database_name', 'unknown')}."
    if name == "get_hm3_schema_overview":
        return f"Loaded schema overview with {len(output.get('tables', []))} tables."
    if name == "get_hm3_stat_mappings":
        return f"Loaded {len(output.get('stat_mappings', []))} stat mappings."
    if name == "get_player_action_patterns":
        return f"Checked action patterns for {output.get('sample_size', 0)} hero hands."
    if name == "get_agent_knowledge":
        return f"Loaded knowledge topic {output.get('topic', 'unknown')}."
    if name == "create_explorer_snapshot":
        return f"Created snapshot {output.get('snapshot_name') or 'none'}."
    if name == "get_leak_finder_context":
        leaks = output.get("deterministic_leak_report", {}).get("leaks", [])
        return f"Loaded leak context with {len(leaks)} fallback signals."
    if name == "get_study_plan_context":
        areas = output.get("deterministic_study_plan", {}).get("focus_areas", [])
        return f"Loaded study context with {len(areas)} fallback focus areas."
    if name == "get_coaching_principles":
        return "Loaded local coaching principles."
    if name == "create_study_drill":
        return f"Created drill for {len(output.get('hand_ids', []))} hands."
    return f"Ran {name}."
