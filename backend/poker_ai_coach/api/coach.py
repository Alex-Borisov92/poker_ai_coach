from fastapi import APIRouter, HTTPException

from poker_ai_coach.agent.deep_jobs import get_deep_analysis_job, start_deep_analysis
from poker_ai_coach.agent.runtime import run_agent_chat
from poker_ai_coach.coach.service import (
    analyze_leaks,
    analyze_overview,
    chat_with_coach,
    explain_study_plan,
    review_hand,
)
from poker_ai_coach.config import get_settings
from poker_ai_coach.models.coach import (
    AgentChatRequest,
    AgentChatResponse,
    CoachChatRequest,
    CoachResponse,
    DeepAnalysisJob,
    DeepAnalysisRequest,
    HandReviewRequest,
)
from poker_ai_coach.reports.coach_scout import build_coach_scout_report
from poker_ai_coach.reports.hand_review_queue import build_review_queue, get_hand_detail
from poker_ai_coach.reports.leak_finder import build_leak_finder_report
from poker_ai_coach.reports.overview import build_overview_report
from poker_ai_coach.reports.study_plan import build_study_plan

router = APIRouter(prefix="/api/coach", tags=["coach"])


@router.post("/analyze-overview", response_model=CoachResponse)
def analyze_overview_report() -> CoachResponse:
    settings = get_settings()
    overview = build_overview_report(settings)
    return analyze_overview(settings, overview)


@router.post("/analyze-leaks", response_model=CoachResponse)
def analyze_leak_finder_report() -> CoachResponse:
    settings = get_settings()
    leak_report = build_leak_finder_report(settings)
    return analyze_leaks(settings, leak_report)


@router.post("/study-plan", response_model=CoachResponse)
def explain_weekly_study_plan() -> CoachResponse:
    settings = get_settings()
    study_plan = build_study_plan(settings)
    return explain_study_plan(settings, study_plan)


@router.post("/review-hand", response_model=CoachResponse)
def review_selected_hand(request: HandReviewRequest) -> CoachResponse:
    settings = get_settings()
    hand = get_hand_detail(settings, request.hand_id)
    return review_hand(settings, hand)


@router.post("/chat", response_model=CoachResponse)
def coach_chat(request: CoachChatRequest) -> CoachResponse:
    settings = get_settings()
    context: dict[str, object] = {}
    use_default_context = not (
        request.context.include_overview
        or request.context.include_leak_report
        or request.context.include_study_plan
        or request.context.hand_id is not None
    )

    if request.context.include_overview or use_default_context:
        if use_default_context:
            context["coach_scout_report"] = build_coach_scout_report(settings)
        else:
            context["overview_report"] = build_overview_report(settings).model_dump()
    if request.context.include_leak_report or use_default_context:
        context["leak_report"] = build_leak_finder_report(settings).model_dump()
    if request.context.include_study_plan or use_default_context:
        context["study_plan"] = build_study_plan(settings).model_dump()
    if use_default_context:
        queue = build_review_queue(settings, limit=10)
        queue_data = queue.model_dump()
        queue_data["warnings"] = [
            warning
            for warning in queue.warnings
            if "error_hands.handhistory_id is missing" not in warning
        ]
        context["selected_review_hands"] = queue_data
    if request.context.hand_id is not None:
        context["selected_hand"] = get_hand_detail(settings, request.context.hand_id).model_dump()

    return chat_with_coach(settings, request, context)


@router.post("/agent-chat", response_model=AgentChatResponse)
def coach_agent_chat(request: AgentChatRequest) -> AgentChatResponse:
    return run_agent_chat(get_settings(), request)


@router.post("/deep-analysis", response_model=DeepAnalysisJob)
def start_coach_deep_analysis(request: DeepAnalysisRequest) -> DeepAnalysisJob:
    return start_deep_analysis(get_settings(), request)


@router.get("/jobs/{job_id}", response_model=DeepAnalysisJob)
def get_coach_job(job_id: str) -> DeepAnalysisJob:
    job = get_deep_analysis_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Coach job not found.")
    return job
