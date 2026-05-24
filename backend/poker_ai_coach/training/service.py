from pathlib import Path

from poker_ai_coach.config import Settings
from poker_ai_coach.db.hm3_connection import connect_readonly
from poker_ai_coach.db.schema_probe import list_tables
from poker_ai_coach.models.training import (
    TrainingCompareResponse,
    TrainingLeak,
    TrainingRunCreateResponse,
    TrainingRunDetail,
    TrainingRunList,
)
from poker_ai_coach.reports.deep_leaks import (
    find_stat_leaks,
    get_monthly_hm3_stats,
    study_items_from_leaks,
)
from poker_ai_coach.reports.overview import get_date_coverage
from poker_ai_coach.training.state_store import (
    compare_latest_training_run,
    create_training_run,
    get_training_run,
    list_training_runs,
)


def create_training_from_current_db(settings: Settings) -> TrainingRunCreateResponse:
    database_path = settings.hm3_db_path
    if database_path is None:
        return TrainingRunCreateResponse(
            created=False,
            warnings=["HM3_DB_PATH is not configured."],
            error="Database is not configured.",
        )

    database_name = Path(database_path).name
    try:
        with connect_readonly(database_path) as connection:
            tables = set(list_tables(connection))
            total_hands = count_hands(connection, tables)
            max_hand_id = max_hand_id_for_db(connection, tables)
            _date_range, valid_hand_count, invalid_1970_count, date_warnings = get_date_coverage(
                connection, tables
            )
    except Exception as exc:
        return TrainingRunCreateResponse(
            created=False,
            warnings=[str(exc)],
            error="Could not create training run from the current database.",
        )

    monthly = get_monthly_hm3_stats(settings)
    latest_valid_month = monthly.get("period")
    leak_result = find_stat_leaks(settings, latest_valid_month, limit=10)
    leaks = [leak_from_dict(item) for item in leak_result.get("leaks", [])]
    study_items = study_items_from_leaks(leaks)
    stats = monthly.get("stats", {})
    initial_summary = build_initial_summary(stats, latest_valid_month)
    warnings = [*date_warnings, *monthly.get("warnings", []), *leak_result.get("warnings", [])]

    return create_training_run(
        database_name=database_name,
        hero_name=settings.hero_name,
        model=settings.openai_model,
        total_hands=total_hands,
        valid_hand_count=valid_hand_count,
        invalid_1970_count=invalid_1970_count,
        max_hand_id=max_hand_id,
        latest_valid_month=latest_valid_month,
        initial_summary=initial_summary,
        warnings=sorted(set(warnings)),
        leaks=leaks,
        study_items=study_items,
    )


def get_training_runs() -> TrainingRunList:
    return list_training_runs()


def get_training_detail(training_run_id: int) -> TrainingRunDetail | None:
    return get_training_run(training_run_id)


def compare_training_with_previous(training_run_id: int) -> TrainingCompareResponse:
    return compare_latest_training_run(training_run_id)


def count_hands(connection, tables: set[str]) -> int:
    if "handhistories" not in tables:
        return 0
    row = connection.execute("SELECT COUNT(*) AS count FROM handhistories").fetchone()
    return int(row["count"] or 0)


def max_hand_id_for_db(connection, tables: set[str]) -> int | None:
    if "handhistories" not in tables:
        return None
    row = connection.execute(
        "SELECT MAX(handhistory_id) AS max_hand_id FROM handhistories"
    ).fetchone()
    value = row["max_hand_id"]
    return int(value) if value is not None else None


def leak_from_dict(value: dict) -> TrainingLeak:
    return TrainingLeak.model_validate(value)


def build_initial_summary(stats: dict, latest_valid_month: str | None) -> str:
    if not stats:
        return "Training created. HM3 aggregate stats are not available yet."
    return (
        f"Training created for {latest_valid_month or 'latest data'}: "
        f"{stats.get('total_hands', 0)} hands, bb/100 {stats.get('bb100')}, "
        f"VPIP/PFR {stats.get('vpip_pct')}/{stats.get('pfr_pct')}."
    )
