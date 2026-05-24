from fastapi import APIRouter, Query

from poker_ai_coach.config import get_settings
from poker_ai_coach.models.hands import HandDetail, HandReviewQueue
from poker_ai_coach.reports.hand_review_queue import build_review_queue, get_hand_detail

router = APIRouter(prefix="/api/hands", tags=["hands"])


@router.get("/review-queue", response_model=HandReviewQueue)
def review_queue(limit: int = Query(default=50, ge=1, le=100)) -> HandReviewQueue:
    return build_review_queue(get_settings(), limit=limit)


@router.get("/{hand_id}", response_model=HandDetail)
def hand_detail(hand_id: int) -> HandDetail:
    return get_hand_detail(get_settings(), hand_id=hand_id)
