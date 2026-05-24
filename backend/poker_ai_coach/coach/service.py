from poker_ai_coach.coach.adapters import CoachAdapter
from poker_ai_coach.coach.mock_adapter import MockCoachAdapter
from poker_ai_coach.coach.openai_adapter import OpenAICompatibleAdapter
from poker_ai_coach.coach.prompts import (
    SYSTEM_PROMPT,
    chat_user_prompt,
    hand_user_prompt,
    leaks_user_prompt,
    model_to_json,
    overview_user_prompt,
    study_plan_user_prompt,
)
from poker_ai_coach.config import Settings
from poker_ai_coach.models.coach import CoachChatRequest, CoachResponse
from poker_ai_coach.models.hands import HandDetail
from poker_ai_coach.models.reports import LeakFinderReport, OverviewReport
from poker_ai_coach.models.study import StudyPlan

MISSING_API_KEY_WARNING = (
    "OPENAI_API_KEY is not configured. Set it in .env or keep AI_ENABLED=false."
)


def ai_configured(settings: Settings) -> bool:
    return settings.ai_enabled and bool(settings.openai_api_key)


def build_adapter(settings: Settings) -> CoachAdapter:
    if ai_configured(settings):
        return OpenAICompatibleAdapter(
            api_key=str(settings.openai_api_key),
            model=settings.openai_model,
        )
    return MockCoachAdapter()


def disabled_response(settings: Settings, adapter: CoachAdapter) -> CoachResponse:
    warnings = []
    if not settings.ai_enabled:
        warnings.append("AI_ENABLED is false.")
    if settings.ai_enabled and not settings.openai_api_key:
        warnings.append(MISSING_API_KEY_WARNING)
    return CoachResponse(
        ai_enabled=settings.ai_enabled,
        ai_configured=False,
        provider=adapter.provider,
        model=adapter.model,
        content=(
            "AI coach is disabled or missing configuration. No data was sent to an AI provider."
        ),
        warnings=warnings,
    )


def analyze_overview(
    settings: Settings,
    overview: OverviewReport,
    adapter: CoachAdapter | None = None,
) -> CoachResponse:
    selected_adapter = adapter or build_adapter(settings)
    if not ai_configured(settings):
        return disabled_response(settings, selected_adapter)

    try:
        content = selected_adapter.complete(
            SYSTEM_PROMPT,
            overview_user_prompt(model_to_json(overview)),
        )
    except Exception as exc:
        return CoachResponse(
            ai_enabled=settings.ai_enabled,
            ai_configured=True,
            provider=selected_adapter.provider,
            model=selected_adapter.model,
            warnings=["AI provider request failed."],
            error=str(exc),
        )

    return CoachResponse(
        ai_enabled=settings.ai_enabled,
        ai_configured=True,
        provider=selected_adapter.provider,
        model=selected_adapter.model,
        content=content,
    )


def analyze_leaks(
    settings: Settings,
    leak_report: LeakFinderReport,
    adapter: CoachAdapter | None = None,
) -> CoachResponse:
    selected_adapter = adapter or build_adapter(settings)
    if not ai_configured(settings):
        return disabled_response(settings, selected_adapter)

    try:
        content = selected_adapter.complete(
            SYSTEM_PROMPT,
            leaks_user_prompt(model_to_json(leak_report)),
        )
    except Exception as exc:
        return CoachResponse(
            ai_enabled=settings.ai_enabled,
            ai_configured=True,
            provider=selected_adapter.provider,
            model=selected_adapter.model,
            warnings=["AI provider request failed."],
            error=str(exc),
        )

    return CoachResponse(
        ai_enabled=settings.ai_enabled,
        ai_configured=True,
        provider=selected_adapter.provider,
        model=selected_adapter.model,
        content=content,
    )


def explain_study_plan(
    settings: Settings,
    study_plan: StudyPlan,
    adapter: CoachAdapter | None = None,
) -> CoachResponse:
    selected_adapter = adapter or build_adapter(settings)
    if not ai_configured(settings):
        return disabled_response(settings, selected_adapter)

    try:
        content = selected_adapter.complete(
            SYSTEM_PROMPT,
            study_plan_user_prompt(model_to_json(study_plan)),
        )
    except Exception as exc:
        return CoachResponse(
            ai_enabled=settings.ai_enabled,
            ai_configured=True,
            provider=selected_adapter.provider,
            model=selected_adapter.model,
            warnings=["AI provider request failed."],
            error=str(exc),
        )

    return CoachResponse(
        ai_enabled=settings.ai_enabled,
        ai_configured=True,
        provider=selected_adapter.provider,
        model=selected_adapter.model,
        content=content,
    )


def review_hand(
    settings: Settings,
    hand: HandDetail,
    adapter: CoachAdapter | None = None,
) -> CoachResponse:
    selected_adapter = adapter or build_adapter(settings)
    if not ai_configured(settings):
        return disabled_response(settings, selected_adapter)
    if hand.error or not hand.hand_text.strip():
        return CoachResponse(
            ai_enabled=settings.ai_enabled,
            ai_configured=True,
            provider=selected_adapter.provider,
            model=selected_adapter.model,
            warnings=["Selected hand is unavailable or has empty text."],
            error=hand.error or "Hand text is empty.",
        )

    hand_metadata = hand.model_copy(update={"hand_text": ""})
    try:
        content = selected_adapter.complete(
            SYSTEM_PROMPT,
            hand_user_prompt(model_to_json(hand_metadata), hand.hand_text),
        )
    except Exception as exc:
        return CoachResponse(
            ai_enabled=settings.ai_enabled,
            ai_configured=True,
            provider=selected_adapter.provider,
            model=selected_adapter.model,
            warnings=["AI provider request failed."],
            error=str(exc),
        )

    return CoachResponse(
        ai_enabled=settings.ai_enabled,
        ai_configured=True,
        provider=selected_adapter.provider,
        model=selected_adapter.model,
        content=content,
    )


def chat_with_coach(
    settings: Settings,
    request: CoachChatRequest,
    context: dict[str, object],
    adapter: CoachAdapter | None = None,
) -> CoachResponse:
    selected_adapter = adapter or build_adapter(settings)
    if not ai_configured(settings):
        return disabled_response(settings, selected_adapter)

    if not context:
        return CoachResponse(
            ai_enabled=settings.ai_enabled,
            ai_configured=True,
            provider=selected_adapter.provider,
            model=selected_adapter.model,
            content="Select an overview, leak report, study plan, or historical hand first.",
            warnings=["No coach chat context was selected."],
        )

    try:
        content = selected_adapter.complete(
            SYSTEM_PROMPT,
            chat_user_prompt(request.message, model_to_json_dict(context)),
        )
    except Exception as exc:
        return CoachResponse(
            ai_enabled=settings.ai_enabled,
            ai_configured=True,
            provider=selected_adapter.provider,
            model=selected_adapter.model,
            warnings=["AI provider request failed."],
            error=str(exc),
        )

    return CoachResponse(
        ai_enabled=settings.ai_enabled,
        ai_configured=True,
        provider=selected_adapter.provider,
        model=selected_adapter.model,
        content=content,
    )


def model_to_json_dict(value: dict[str, object]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
