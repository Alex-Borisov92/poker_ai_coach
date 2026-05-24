from fastapi.testclient import TestClient
from poker_ai_coach.coach.service import (
    analyze_leaks,
    analyze_overview,
    chat_with_coach,
    explain_study_plan,
    review_hand,
)
from poker_ai_coach.config import Settings
from poker_ai_coach.main import app
from poker_ai_coach.models.coach import CoachChatContext, CoachChatRequest
from poker_ai_coach.models.hands import HandDetail
from poker_ai_coach.models.reports import (
    DateRange,
    LeakFinderItem,
    LeakFinderReport,
    OverviewReport,
)
from poker_ai_coach.models.study import StudyFocusArea, StudyPlan


class FakeCoachAdapter:
    provider = "fake"
    model = "fake-model"

    def __init__(self) -> None:
        self.system_prompt = ""
        self.user_prompt = ""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return "1. Main leak\nMocked coach response."


def test_analyze_overview_uses_adapter_with_report_json_only():
    adapter = FakeCoachAdapter()
    settings = Settings(AI_ENABLED=True, OPENAI_API_KEY="test-key", OPENAI_MODEL="test-model")
    overview = OverviewReport(
        configured=True,
        connected=True,
        database_name="tiny.hmdb",
        hero_name="surok_valera",
        hero_found=True,
        total_hands=12,
        tournaments=2,
        imported_files=1,
        error_hands=0,
        valid_date_range=DateRange(start="2026-05-20", end="2026-05-21"),
        valid_date_count=12,
        invalid_1970_date_count=0,
    )

    response = analyze_overview(settings, overview, adapter=adapter)

    assert response.ai_configured is True
    assert response.provider == "fake"
    assert "Mocked coach response" in response.content
    assert '"total_hands": 12' in adapter.user_prompt
    assert "Do not give advice for active hands" in adapter.system_prompt
    assert "Prioritize poker decisions over database cleanup." in adapter.system_prompt
    assert "tournaments up to $15 buy-in" in adapter.system_prompt
    assert "hero text is missing" in adapter.system_prompt
    assert "Core Microstakes MTT Doctrine" in adapter.system_prompt
    assert "Small pots - steal." in adapter.system_prompt
    assert "Do not mention VPIP, PFR, 3bet" in adapter.user_prompt
    assert "test-key" not in adapter.user_prompt


def test_review_hand_uses_adapter_with_selected_hand_text():
    adapter = FakeCoachAdapter()
    settings = Settings(AI_ENABLED=True, OPENAI_API_KEY="test-key", OPENAI_MODEL="test-model")
    hand = HandDetail(
        configured=True,
        connected=True,
        hand_id=42,
        tournament_number="T-42",
        hand_date="2026-05-20",
        source="handhistories",
        hand_text="Poker hand #42\nsurok_valera raises and villain goes all-in.",
    )

    response = review_hand(settings, hand, adapter=adapter)

    assert response.ai_configured is True
    assert "Mocked coach response" in response.content
    assert '"hand_id": 42' in adapter.user_prompt
    assert "villain goes all-in" in adapter.user_prompt
    assert "test-key" not in adapter.user_prompt


def test_analyze_leaks_uses_adapter_with_leak_report_json_only():
    adapter = FakeCoachAdapter()
    settings = Settings(AI_ENABLED=True, OPENAI_API_KEY="test-key", OPENAI_MODEL="test-model")
    report = LeakFinderReport(
        configured=True,
        connected=True,
        database_name="tiny.hmdb",
        hero_name="surok_valera",
        total_hands=50,
        leaks=[
            LeakFinderItem(
                leak_key="all_in_review_volume",
                leak_name="All-in review volume",
                evidence="8 of 50 hands contain all-in text.",
                confidence="medium",
                recommended_action="Review all-in hands manually.",
                related_hand_ids=[1, 2],
            )
        ],
    )

    response = analyze_leaks(settings, report, adapter=adapter)

    assert response.ai_configured is True
    assert "Mocked coach response" in response.content
    assert '"leak_key": "all_in_review_volume"' in adapter.user_prompt
    assert "Do not invent VPIP, PFR, 3bet" in adapter.user_prompt
    assert "test-key" not in adapter.user_prompt


def test_explain_study_plan_uses_adapter_with_plan_json_only():
    adapter = FakeCoachAdapter()
    settings = Settings(AI_ENABLED=True, OPENAI_API_KEY="test-key", OPENAI_MODEL="test-model")
    plan = StudyPlan(
        configured=True,
        connected=True,
        hero_name="surok_valera",
        focus_areas=[
            StudyFocusArea(
                title="All-in review volume",
                evidence="8 hands contain all-in text.",
                confidence="medium",
                action="Review all-in hands manually.",
            )
        ],
        drills=["Review all-in hands and write stack depth."],
        weekly_checklist=["Review 5 hands."],
        confidence="medium",
    )

    response = explain_study_plan(settings, plan, adapter=adapter)

    assert response.ai_configured is True
    assert "Mocked coach response" in response.content
    assert '"focus_areas"' in adapter.user_prompt
    assert "Do not invent unsupported stats" in adapter.user_prompt
    assert "test-key" not in adapter.user_prompt


def test_coach_chat_uses_adapter_with_selected_context_only():
    adapter = FakeCoachAdapter()
    settings = Settings(AI_ENABLED=True, OPENAI_API_KEY="test-key", OPENAI_MODEL="test-model")
    request = CoachChatRequest(
        message="What should I study first?",
        context=CoachChatContext(include_overview=True),
    )
    context = {
        "overview_report": {
            "hero_name": "surok_valera",
            "total_hands": 20,
            "invalid_1970_date_count": 3,
        }
    }

    response = chat_with_coach(settings, request, context, adapter=adapter)

    assert response.ai_configured is True
    assert "Mocked coach response" in response.content
    assert "User question:" in adapter.user_prompt
    assert "What should I study first?" in adapter.user_prompt
    assert '"overview_report"' in adapter.user_prompt
    assert '"total_hands": 20' in adapter.user_prompt
    assert "using only the provided context" in adapter.user_prompt.lower()
    assert "start with the most useful poker study priorities" in adapter.user_prompt
    assert "Do not make missing hero" in adapter.user_prompt
    assert "coach_scout_report is present" in adapter.user_prompt
    assert "Do not request arbitrary SQL access" in adapter.user_prompt
    assert "test-key" not in adapter.user_prompt


def test_coach_chat_asks_for_context_when_missing():
    adapter = FakeCoachAdapter()
    settings = Settings(AI_ENABLED=True, OPENAI_API_KEY="test-key", OPENAI_MODEL="test-model")
    request = CoachChatRequest(message="What is my main leak?")

    response = chat_with_coach(settings, request, {}, adapter=adapter)

    assert response.ai_configured is True
    assert "Select an overview" in response.content
    assert "No coach chat context was selected." in response.warnings
    assert adapter.user_prompt == ""


def test_analyze_overview_returns_disabled_when_ai_is_off():
    adapter = FakeCoachAdapter()
    settings = Settings(AI_ENABLED=False, OPENAI_API_KEY=None)
    overview = OverviewReport(configured=False, connected=False, hero_name="surok_valera")

    response = analyze_overview(settings, overview, adapter=adapter)

    assert response.ai_enabled is False
    assert response.ai_configured is False
    assert "AI_ENABLED is false." in response.warnings
    assert adapter.user_prompt == ""


def test_analyze_overview_returns_clear_warning_when_api_key_is_missing():
    adapter = FakeCoachAdapter()
    settings = Settings(AI_ENABLED=True, OPENAI_API_KEY=None)
    overview = OverviewReport(configured=False, connected=False, hero_name="surok_valera")

    response = analyze_overview(settings, overview, adapter=adapter)

    assert response.ai_enabled is True
    assert response.ai_configured is False
    assert "OPENAI_API_KEY is not configured. Set it in .env or keep AI_ENABLED=false." in (
        response.warnings
    )
    assert adapter.user_prompt == ""


def test_analyze_overview_endpoint_is_safe_when_ai_disabled(monkeypatch):
    monkeypatch.delenv("HM3_DB_PATH", raising=False)
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post("/api/coach/analyze-overview")

    assert response.status_code == 200
    data = response.json()
    assert data["ai_enabled"] is False
    assert data["ai_configured"] is False
    assert "No data was sent to an AI provider." in data["content"]


def test_review_hand_endpoint_is_safe_when_ai_disabled(monkeypatch):
    monkeypatch.delenv("HM3_DB_PATH", raising=False)
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post("/api/coach/review-hand", json={"hand_id": 42})

    assert response.status_code == 200
    data = response.json()
    assert data["ai_enabled"] is False
    assert data["ai_configured"] is False
    assert "AI_ENABLED is false." in data["warnings"]


def test_coach_chat_endpoint_is_safe_when_ai_disabled(monkeypatch):
    monkeypatch.delenv("HM3_DB_PATH", raising=False)
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post(
        "/api/coach/chat",
        json={
            "message": "What should I study?",
            "context": {"include_overview": True, "include_leak_report": True},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ai_enabled"] is False
    assert data["ai_configured"] is False
    assert "No data was sent to an AI provider." in data["content"]
