import uuid

from poker_ai_coach.agent.runtime import summarize_tool_output
from poker_ai_coach.config import Settings
from poker_ai_coach.models.coach import AgentToolStep, DeepAnalysisJob, DeepAnalysisRequest
from poker_ai_coach.models.training import TrainingLeak
from poker_ai_coach.reports.deep_leaks import (
    analyze_hand_actions_batch,
    find_stat_leaks,
    get_candidate_hands_for_leak,
    get_monthly_hm3_stats,
    study_items_from_leaks,
)
from poker_ai_coach.training.state_store import save_training_text

_JOBS: dict[str, DeepAnalysisJob] = {}


def start_deep_analysis(settings: Settings, request: DeepAnalysisRequest) -> DeepAnalysisJob:
    job_id = str(uuid.uuid4())
    job = DeepAnalysisJob(
        job_id=job_id,
        status="running",
        mode=request.mode,
        training_run_id=request.training_run_id,
    )
    _JOBS[job_id] = job
    try:
        completed = run_deep_analysis(settings, request, job_id)
    except Exception as exc:
        completed = job.model_copy(
            update={"status": "error", "error": f"Deep analysis failed: {exc}"}
        )
    _JOBS[job_id] = completed
    return completed


def get_deep_analysis_job(job_id: str) -> DeepAnalysisJob | None:
    return _JOBS.get(job_id)


def run_deep_analysis(
    settings: Settings,
    request: DeepAnalysisRequest,
    job_id: str,
) -> DeepAnalysisJob:
    period = request.period
    steps: list[AgentToolStep] = []
    monthly = get_monthly_hm3_stats(settings, period)
    steps.append(
        AgentToolStep(
            name="get_monthly_hm3_stats",
            arguments={"period": period},
            summary=f"Loaded monthly stats for {monthly.get('period') or 'unknown period'}.",
        )
    )
    leak_result = find_stat_leaks(settings, monthly.get("period"), request.limit)
    steps.append(
        AgentToolStep(
            name="find_stat_leaks",
            arguments={"period": monthly.get("period"), "limit": request.limit},
            summary=f"Found {len(leak_result.get('leaks', []))} structured leaks.",
        )
    )
    leaks = leak_result.get("leaks", [])
    all_hand_ids: list[int] = []
    for leak in leaks:
        hand_result = get_candidate_hands_for_leak(
            settings,
            str(leak["leak_key"]),
            monthly.get("period"),
            3,
        )
        steps.append(
            AgentToolStep(
                name="get_candidate_hands_for_leak",
                arguments={"leak_key": leak["leak_key"], "period": monthly.get("period")},
                summary=f"Found {len(hand_result.get('hands', []))} hand examples.",
            )
        )
        hand_ids = [int(hand["hand_id"]) for hand in hand_result.get("hands", [])]
        leak["related_hand_ids"] = hand_ids
        all_hand_ids.extend(hand_ids)
    unique_hand_ids = unique_ids(all_hand_ids)[:10]
    hand_analyses = analyze_hand_actions_batch(settings, unique_hand_ids, 10)
    steps.append(
        AgentToolStep(
            name="analyze_hand_actions_batch",
            arguments={"hand_ids": unique_hand_ids},
            summary=summarize_tool_output("get_hand_detail", {"hand_id": unique_hand_ids[:1]}),
        )
    )
    leak_models = [TrainingLeak.model_validate(leak) for leak in leaks if isinstance(leak, dict)]
    study_items = [item.model_dump() for item in study_items_from_leaks(leak_models)]
    content = compose_deep_content(monthly, leaks, hand_analyses.get("hands", []), study_items)
    if request.training_run_id is not None:
        if request.mode in {"study_plan_deep", "training_initial", "training_followup"}:
            save_training_text(request.training_run_id, study_plan_result=content)
        else:
            save_training_text(request.training_run_id, deep_leak_result=content)
    return DeepAnalysisJob(
        job_id=job_id,
        status="completed",
        mode=request.mode,
        training_run_id=request.training_run_id,
        content=content,
        leaks=leaks,
        hand_analyses=hand_analyses.get("hands", []),
        study_items=study_items,
        steps=steps,
        warnings=[
            *monthly.get("warnings", []),
            *leak_result.get("warnings", []),
            *hand_analyses.get("warnings", []),
        ],
    )


def compose_deep_content(
    monthly: dict,
    leaks: list[dict],
    hands: list[dict],
    study_items: list[dict],
) -> str:
    stats = monthly.get("stats", {})
    lines = [
        "## Main takeaway",
        (
            f"Latest available period {monthly.get('period') or 'unknown'}: "
            f"{stats.get('total_hands', 0)} hands, bb/100 {stats.get('bb100')}."
        ),
        "Coach focus: connect HM3 stats to concrete expensive decisions.",
        "",
        "## 10 leak candidates",
    ]
    for leak in leaks:
        lines.extend(
            [
                f"- {leak.get('severity', 'medium').upper()}: {leak.get('title')}",
                f"  Evidence: {leak.get('evidence')}",
                f"  Coach read: {leak.get('coach_read')}",
                "  Hands: "
                + ", ".join(str(hand_id) for hand_id in leak.get("related_hand_ids", [])),
            ]
        )
    lines.extend(["", "## Hand breakdown"])
    for hand in hands[:10]:
        lines.extend(
            [
                f"- Hand {hand.get('hand_id')}",
                (
                    f"  Situation: position {hand.get('hero_position') or 'unknown'}, "
                    f"stack {hand.get('hero_stack_bb') or 'unknown'}bb, "
                    f"actions {', '.join(hand.get('hero_actions', [])) or 'unknown'}."
                ),
                f"  What to check: {' '.join(hand.get('coach_questions', []))}",
                f"  Excerpt: {hand.get('hand_text_excerpt') or 'No excerpt available.'}",
            ]
        )
    lines.extend(["", "## Study plan"])
    for item in study_items:
        lines.extend(
            [
                f"- {item.get('title')}: {item.get('drill')}",
                f"  Checklist: {', '.join(item.get('checklist', []))}",
            ]
        )
    lines.extend(
        [
            "",
            "## Limits",
            (
                "These are coaching hypotheses from HM3 counters and selected "
                "historical hands, not solver output."
            ),
        ]
    )
    return "\n".join(lines)


def unique_ids(values: list[int]) -> list[int]:
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
