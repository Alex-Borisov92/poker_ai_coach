from poker_ai_coach.config import Settings
from poker_ai_coach.models.hands import HandSummary
from poker_ai_coach.models.reports import LeakFinderItem
from poker_ai_coach.models.study import StudyFocusArea, StudyHand, StudyPlan
from poker_ai_coach.reports.hand_review_queue import build_review_queue
from poker_ai_coach.reports.leak_finder import build_leak_finder_report

CONFIDENCE_ORDER = {"high": 3, "medium": 2, "low": 1}
FOCUS_PRIORITY = {
    "review_category_large_pot": 120,
    "review_category_all_in": 115,
    "selected_tournament_cluster": 112,
    "all_in_review_volume": 105,
    "tournament_result_pressure": 95,
    "hm3_import_errors": 60,
    "tournament_result_coverage": 45,
    "hero_text_partial": 40,
    "hero_text_missing": 40,
    "invalid_date_coverage": 30,
}


def confidence_from_focus(focus_areas: list[StudyFocusArea]) -> str:
    if not focus_areas:
        return "low"
    best_score = max(CONFIDENCE_ORDER.get(area.confidence, 1) for area in focus_areas)
    if best_score >= 3:
        return "high"
    if best_score == 2:
        return "medium"
    return "low"


def drill_for_leak(leak: LeakFinderItem) -> str:
    if leak.leak_key == "review_category_large_pot":
        return "Review large pots and write value target, bluff target, and SPR pressure."
    if leak.leak_key == "review_category_all_in":
        return "Review marked all-ins and write stack depth, fold equity, and bounty context."
    if leak.leak_key == "all_in_review_volume":
        return "Review all-in hands and write stack depth, fold equity, and bounty context."
    if leak.leak_key == "selected_tournament_cluster":
        return "Review the clustered tournament from first marked pot to final marked hand."
    if leak.leak_key == "tournament_result_pressure":
        return "Check whether losing results came from all-ins, large pots, or late-stage pressure."
    if leak.leak_key in {"invalid_date_coverage", "tournament_result_coverage"}:
        return "Check data quality before judging session results or date-filtered trends."
    if leak.leak_key == "hm3_import_errors":
        return "Open import-error hands first and mark whether the hand text is usable."
    if leak.leak_key in {"hero_text_missing", "hero_text_partial"}:
        return "Verify HERO_NAME and nickname spelling before trusting text-derived categories."
    if "large_pot" in leak.leak_key:
        return "For each big pot, write value target, bluff target, and street where SPR got low."
    return f"Review '{leak.leak_name}' hands and write one exploitative adjustment."


def weekly_checklist() -> list[str]:
    return [
        "Review 5-10 marked hands before opening more tables.",
        "Write one leak hypothesis and one missing-data note.",
        "Pick one drill for the next session.",
        "After the session, compare decisions with the same drill.",
    ]


def sorted_leaks(leaks: list[LeakFinderItem]) -> list[LeakFinderItem]:
    return sorted(
        leaks,
        key=lambda leak: (
            FOCUS_PRIORITY.get(leak.leak_key, 50),
            CONFIDENCE_ORDER.get(leak.confidence, 1),
            len(leak.related_hand_ids),
            leak.leak_name,
        ),
        reverse=True,
    )


def unique_hands_from_focus(
    focus_leaks: list[LeakFinderItem], queue_hands: list[HandSummary], limit: int = 10
) -> list[StudyHand]:
    queue_by_id = {hand.hand_id: hand for hand in queue_hands}
    selected_ids: list[int] = []

    for leak in focus_leaks:
        for hand_id in leak.related_hand_ids:
            if hand_id in queue_by_id and hand_id not in selected_ids:
                selected_ids.append(hand_id)

    for hand in queue_hands:
        if hand.hand_id not in selected_ids:
            selected_ids.append(hand.hand_id)
        if len(selected_ids) >= limit:
            break

    study_hands = []
    for hand_id in selected_ids[:limit]:
        hand = queue_by_id[hand_id]
        study_hands.append(
            StudyHand(
                hand_id=hand.hand_id,
                tournament_number=hand.tournament_number,
                hand_date=hand.hand_date,
                reasons=hand.reasons,
                source=hand.source,
            )
        )
    return study_hands


def build_study_plan(settings: Settings) -> StudyPlan:
    leak_report = build_leak_finder_report(settings)
    hand_queue = build_review_queue(settings, limit=50)

    warnings = list(leak_report.warnings)
    missing_data = list(leak_report.missing_data)
    for warning in hand_queue.warnings:
        if "error_hands.handhistory_id is missing" in warning:
            missing_data.append("Import error hands cannot be linked to exact hand IDs.")
        else:
            warnings.append(warning)
    if not hand_queue.hands:
        missing_data.append("No selected hands are available for review.")

    if leak_report.error or hand_queue.error:
        return StudyPlan(
            configured=leak_report.configured and hand_queue.configured,
            connected=leak_report.connected and hand_queue.connected,
            database_name=leak_report.database_name or hand_queue.database_name,
            hero_name=leak_report.hero_name,
            missing_data=sorted(set(missing_data)),
            warnings=warnings,
            error=leak_report.error or hand_queue.error,
        )

    focus_leaks = sorted_leaks(leak_report.leaks)[:3]
    focus_areas = [
        StudyFocusArea(
            title=leak.leak_name,
            evidence=leak.evidence,
            confidence=leak.confidence,
            action=leak.recommended_action,
        )
        for leak in focus_leaks
    ]
    drills = []
    for leak in focus_leaks:
        drill = drill_for_leak(leak)
        if drill not in drills:
            drills.append(drill)

    if not focus_areas:
        warnings.append("No supported leak focus areas found yet.")
        drills.append("Review 5 recent marked hands and write one clear decision mistake.")

    hands_to_review = unique_hands_from_focus(focus_leaks, hand_queue.hands, limit=10)

    return StudyPlan(
        configured=leak_report.configured and hand_queue.configured,
        connected=leak_report.connected and hand_queue.connected,
        database_name=leak_report.database_name or hand_queue.database_name,
        hero_name=leak_report.hero_name,
        focus_areas=focus_areas,
        hands_to_review=hands_to_review,
        drills=drills,
        weekly_checklist=weekly_checklist(),
        confidence=confidence_from_focus(focus_areas),
        missing_data=sorted(set(missing_data)),
        warnings=warnings,
    )
