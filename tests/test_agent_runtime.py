from pathlib import Path

from poker_ai_coach.agent.runtime import run_agent_chat
from poker_ai_coach.agent.tool_registry import execute_tool, tool_definitions
from poker_ai_coach.config import Settings
from poker_ai_coach.models.coach import AgentChatRequest


def create_agent_db(database_path: Path) -> None:
    import sqlite3

    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE handhistories (
            handhistory_id INTEGER PRIMARY KEY,
            tournament_number TEXT,
            handtimestamp TEXT,
            handhistory TEXT
        )
        """
    )
    connection.execute("CREATE TABLE error_hands (error_hand_id INTEGER PRIMARY KEY)")
    connection.execute(
        """
        INSERT INTO handhistories
          (handhistory_id, tournament_number, handtimestamp, handhistory)
        VALUES (
          1,
          'T-1',
          '2026-05-20 10:00:00',
          'Poker Hand #1: Tournament #T-1 - Level5(100/200)
Seat 1: Hero (4000 in chips)
Dealt to Hero [Ah Kh]
Hero: calls 4000 and is all-in
Total pot 8200 | Rake 0'
        )
        """
    )
    connection.commit()
    connection.close()


class FakeResponsesTransport:
    def __init__(self) -> None:
        self.payloads = []
        self.calls = 0

    def create_response(self, payload):
        self.payloads.append(payload)
        self.calls += 1
        if self.calls == 1:
            return {
                "id": "resp_1",
                "output": [
                    {
                        "type": "function_call",
                        "name": "get_database_profile",
                        "call_id": "call_1",
                        "arguments": "{}",
                    }
                ],
            }
        if self.calls == 2:
            return {
                "id": "resp_2",
                "output": [
                    {
                        "type": "function_call",
                        "name": "search_hands",
                        "call_id": "call_2",
                        "arguments": '{"all_in": true, "large_pot": true, "limit": 5}',
                    }
                ],
            }
        return {
            "id": "resp_3",
            "output_text": "Main insight\nEvidence\nHands to open: 1\nDrill",
            "output": [],
        }


class FakeScoutTransport:
    def __init__(self) -> None:
        self.payloads = []

    def create_response(self, payload):
        self.payloads.append(payload)
        return {
            "id": "resp_scout",
            "output_text": "Main insight\nEvidence\nHands to open: 1\nDrill",
            "output": [],
        }


class FakeLoopingTransport:
    def __init__(self) -> None:
        self.payloads = []

    def create_response(self, payload):
        self.payloads.append(payload)
        if payload.get("tools"):
            return {
                "id": f"resp_loop_{len(self.payloads)}",
                "output": [
                    {
                        "type": "function_call",
                        "name": "get_database_profile",
                        "call_id": f"call_{len(self.payloads)}",
                        "arguments": "{}",
                    }
                ],
            }
        return {
            "id": "resp_final",
            "output_text": "Main insight\nEvidence from collected tools\nHands to open\nDrill",
            "output": [],
        }


def test_agent_runtime_executes_local_tools(tmp_path: Path):
    database_path = tmp_path / "agent.hmdb"
    create_agent_db(database_path)
    settings = Settings(
        HM3_DB_PATH=database_path,
        HERO_NAME="surok_valera",
        AI_ENABLED=True,
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-5-mini",
    )
    transport = FakeResponsesTransport()

    response = run_agent_chat(
        settings,
        AgentChatRequest(message="Review selected hand", mode="hand_review"),
        transport=transport,
    )

    assert response.ai_configured is True
    assert response.provider == "openai"
    assert response.content.startswith("Main insight")
    assert [step.name for step in response.tool_steps] == ["get_database_profile", "search_hands"]
    assert response.selected_hand_ids == [1]
    assert len(transport.payloads) == 3
    assert "tools" in transport.payloads[0]
    assert "test-key" not in str(transport.payloads)


def test_database_scout_mode_uses_fixed_safe_tool_bundle(tmp_path: Path):
    database_path = tmp_path / "agent.hmdb"
    create_agent_db(database_path)
    settings = Settings(
        HM3_DB_PATH=database_path,
        HERO_NAME="surok_valera",
        AI_ENABLED=True,
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-5-mini",
    )
    transport = FakeScoutTransport()

    response = run_agent_chat(
        settings,
        AgentChatRequest(message="Run database scout", mode="database_scout"),
        transport=transport,
    )

    assert response.content.startswith("Main insight")
    assert [step.name for step in response.tool_steps] == [
        "get_database_profile",
        "get_hm3_schema_overview",
        "get_hm3_player_stats",
        "get_hm3_stat_mappings",
        "get_coaching_principles",
        "get_coach_scout_report",
        "search_hands",
        "create_study_drill",
    ]
    assert response.selected_hand_ids == [1]
    assert len(transport.payloads) == 1
    assert "tools" not in transport.payloads[0]
    assert "test-key" not in str(transport.payloads)


def test_overview_question_auto_uses_database_scout(tmp_path: Path):
    database_path = tmp_path / "agent.hmdb"
    create_agent_db(database_path)
    settings = Settings(
        HM3_DB_PATH=database_path,
        HERO_NAME="surok_valera",
        AI_ENABLED=True,
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-5-mini",
    )
    transport = FakeScoutTransport()

    response = run_agent_chat(
        settings,
        AgentChatRequest(message="Give me an overview of my leaks"),
        transport=transport,
    )

    assert response.content.startswith("Main insight")
    assert [step.name for step in response.tool_steps] == [
        "get_database_profile",
        "get_hm3_schema_overview",
        "get_hm3_player_stats",
        "get_hm3_stat_mappings",
        "get_coaching_principles",
        "get_coach_scout_report",
        "search_hands",
        "create_study_drill",
    ]


def test_stats_question_uses_aggregate_stats_without_hand_scan(tmp_path: Path):
    database_path = tmp_path / "agent.hmdb"
    create_agent_db(database_path)
    settings = Settings(
        HM3_DB_PATH=database_path,
        HERO_NAME="surok_valera",
        AI_ENABLED=True,
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-5-mini",
    )
    transport = FakeScoutTransport()

    response = run_agent_chat(
        settings,
        AgentChatRequest(message="Give me my stats overview"),
        transport=transport,
    )

    assert response.content.startswith("Main insight")
    assert [step.name for step in response.tool_steps] == [
        "get_database_profile",
        "get_hm3_schema_overview",
        "get_hm3_player_stats",
        "get_hm3_stat_mappings",
        "get_coaching_principles",
    ]
    assert response.selected_hand_ids == []


def test_russian_stats_question_uses_aggregate_stats_without_hand_scan(tmp_path: Path):
    database_path = tmp_path / "agent.hmdb"
    create_agent_db(database_path)
    settings = Settings(
        HM3_DB_PATH=database_path,
        HERO_NAME="surok_valera",
        AI_ENABLED=True,
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-5-mini",
    )
    transport = FakeScoutTransport()

    response = run_agent_chat(
        settings,
        AgentChatRequest(message="дай овервью по моим статам"),
        transport=transport,
    )

    assert response.content.startswith("Main insight")
    assert [step.name for step in response.tool_steps] == [
        "get_database_profile",
        "get_hm3_schema_overview",
        "get_hm3_player_stats",
        "get_hm3_stat_mappings",
        "get_coaching_principles",
    ]
    assert response.selected_hand_ids == []


def test_week_stats_question_uses_period_stats_before_overall_stats(tmp_path: Path):
    database_path = tmp_path / "agent.hmdb"
    create_agent_db(database_path)
    settings = Settings(
        HM3_DB_PATH=database_path,
        HERO_NAME="surok_valera",
        AI_ENABLED=True,
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-5-mini",
    )
    transport = FakeScoutTransport()

    response = run_agent_chat(
        settings,
        AgentChatRequest(message="дай овервью по статам за эту неделю"),
        transport=transport,
    )

    names = [step.name for step in response.tool_steps]

    assert response.content.startswith("Main insight")
    assert names[:4] == [
        "get_database_profile",
        "get_hm3_schema_overview",
        "get_hm3_period_stats",
        "get_hm3_player_stats",
    ]


def test_leak_finder_mode_uses_agent_context_tools(tmp_path: Path):
    database_path = tmp_path / "agent.hmdb"
    create_agent_db(database_path)
    settings = Settings(
        HM3_DB_PATH=database_path,
        HERO_NAME="surok_valera",
        AI_ENABLED=True,
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-5-mini",
    )
    transport = FakeScoutTransport()

    response = run_agent_chat(
        settings,
        AgentChatRequest(message="Find my leaks", mode="leak_finder"),
        transport=transport,
    )

    names = [step.name for step in response.tool_steps]

    assert response.content.startswith("Main insight")
    assert names[:6] == [
        "get_database_profile",
        "get_hm3_player_stats",
        "get_hm3_stat_mappings",
        "get_agent_knowledge",
        "get_agent_knowledge",
        "get_leak_finder_context",
    ]
    assert "search_hands" in names
    assert "create_study_drill" in names


def test_study_plan_mode_uses_agent_context_tools(tmp_path: Path):
    database_path = tmp_path / "agent.hmdb"
    create_agent_db(database_path)
    settings = Settings(
        HM3_DB_PATH=database_path,
        HERO_NAME="surok_valera",
        AI_ENABLED=True,
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-5-mini",
    )
    transport = FakeScoutTransport()

    response = run_agent_chat(
        settings,
        AgentChatRequest(message="Build my plan", mode="study_plan"),
        transport=transport,
    )

    names = [step.name for step in response.tool_steps]

    assert response.content.startswith("Main insight")
    assert "get_study_plan_context" in names
    assert "get_agent_knowledge" in names
    assert "create_study_drill" in names


def test_agent_runtime_forces_final_answer_after_tool_limit(tmp_path: Path):
    database_path = tmp_path / "agent.hmdb"
    create_agent_db(database_path)
    settings = Settings(
        HM3_DB_PATH=database_path,
        HERO_NAME="surok_valera",
        AI_ENABLED=True,
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-5-mini",
    )
    transport = FakeLoopingTransport()

    response = run_agent_chat(
        settings,
        AgentChatRequest(message="Keep searching forever"),
        transport=transport,
    )

    assert response.content.startswith("Main insight")
    assert "Agent stopped" not in response.content
    assert response.warnings == [
        "Maximum tool step limit reached. The agent wrote a final answer from collected evidence."
    ]
    assert "tools" not in transport.payloads[-1]


def test_agent_runtime_disabled_without_api_key(tmp_path: Path):
    settings = Settings(AI_ENABLED=True, OPENAI_API_KEY=None)

    response = run_agent_chat(settings, AgentChatRequest(message="test"))

    assert response.ai_configured is False
    assert "No data was sent to an AI provider." in response.content


def test_tool_registry_has_no_raw_sql_tool():
    names = {tool["name"] for tool in tool_definitions()}

    assert "raw_sql" not in names
    assert "execute_sql" not in names
    assert "get_database_profile" in names
    assert "get_hm3_player_stats" in names
    assert "get_hand_detail" in names


def test_get_coaching_principles_tool_uses_local_file():
    output = execute_tool(Settings(), "get_coaching_principles", {})

    assert "Core Microstakes MTT Doctrine" in output["principles"]
