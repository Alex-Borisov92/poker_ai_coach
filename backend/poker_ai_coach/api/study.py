from fastapi import APIRouter

from poker_ai_coach.config import get_settings
from poker_ai_coach.models.study import StudyPlan
from poker_ai_coach.reports.study_plan import build_study_plan

router = APIRouter(prefix="/api", tags=["study"])


@router.get("/study-plan", response_model=StudyPlan)
def study_plan() -> StudyPlan:
    return build_study_plan(get_settings())
