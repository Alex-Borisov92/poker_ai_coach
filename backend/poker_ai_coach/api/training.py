from fastapi import APIRouter, HTTPException

from poker_ai_coach.config import get_settings
from poker_ai_coach.models.training import (
    TrainingCompareResponse,
    TrainingRunCreateResponse,
    TrainingRunDetail,
    TrainingRunList,
)
from poker_ai_coach.training.service import (
    compare_training_with_previous,
    create_training_from_current_db,
    get_training_detail,
    get_training_runs,
)

router = APIRouter(prefix="/api/training-runs", tags=["training"])


@router.post("", response_model=TrainingRunCreateResponse)
def create_training_run_endpoint() -> TrainingRunCreateResponse:
    return create_training_from_current_db(get_settings())


@router.get("", response_model=TrainingRunList)
def list_training_runs_endpoint() -> TrainingRunList:
    return get_training_runs()


@router.get("/{training_run_id}", response_model=TrainingRunDetail)
def get_training_run_endpoint(training_run_id: int) -> TrainingRunDetail:
    training_run = get_training_detail(training_run_id)
    if training_run is None:
        raise HTTPException(status_code=404, detail="Training run not found.")
    return training_run


@router.post("/{training_run_id}/compare-latest", response_model=TrainingCompareResponse)
def compare_training_run_endpoint(training_run_id: int) -> TrainingCompareResponse:
    return compare_training_with_previous(training_run_id)
