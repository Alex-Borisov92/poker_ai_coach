from fastapi import APIRouter

from poker_ai_coach.config import get_settings
from poker_ai_coach.models.reports import LeakFinderReport, OverviewReport
from poker_ai_coach.reports.leak_finder import build_leak_finder_report
from poker_ai_coach.reports.overview import build_overview_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/overview", response_model=OverviewReport)
def overview_report() -> OverviewReport:
    return build_overview_report(get_settings())


@router.get("/leak-finder", response_model=LeakFinderReport)
def leak_finder_report() -> LeakFinderReport:
    return build_leak_finder_report(get_settings())
