import sqlite3
from pathlib import Path

from poker_ai_coach.models.training import TrainingLeak, TrainingStudyItem
from poker_ai_coach.training.state_store import (
    compare_latest_training_run,
    connect_state_db,
    create_training_run,
    list_training_runs,
)


def test_training_state_creates_runs_and_compares_new_hands(tmp_path: Path):
    state_path = tmp_path / "coach.sqlite"
    leak = TrainingLeak(
        leak_key="passive_preflop_gap",
        title="Passive preflop gap",
        severity="high",
        evidence="VPIP/PFR gap is 6.0%.",
        coach_read="Review flats and missed iso raises.",
        sample_size=1000,
        related_hand_ids=[1, 2, 3],
        confidence="high",
    )
    study_item = TrainingStudyItem(
        title="Passive preflop gap",
        drill="Review passive preflop hands.",
        checklist=["Mark position.", "Choose raise, call, or fold."],
        linked_leak_keys=["passive_preflop_gap"],
        linked_hand_ids=[1, 2],
    )

    first = create_training_run(
        database_name="test.hmdb",
        hero_name="hero",
        model="mock",
        total_hands=100,
        valid_hand_count=90,
        invalid_1970_count=10,
        max_hand_id=100,
        latest_valid_month="202605",
        initial_summary="First run",
        warnings=[],
        leaks=[leak],
        study_items=[study_item],
        path=state_path,
    )
    second = create_training_run(
        database_name="test.hmdb",
        hero_name="hero",
        model="mock",
        total_hands=150,
        valid_hand_count=140,
        invalid_1970_count=10,
        max_hand_id=150,
        latest_valid_month="202605",
        initial_summary="Second run",
        warnings=[],
        leaks=[leak],
        study_items=[study_item],
        path=state_path,
    )

    runs = list_training_runs(state_path)
    compare = compare_latest_training_run(second.training_run.id, state_path)

    assert first.created is True
    assert second.created is True
    assert len(runs.training_runs) == 2
    assert compare.new_hands == 50
    assert compare.leak_changes


def test_training_state_is_separate_from_hm3_read_only_db(tmp_path: Path):
    hm3_path = tmp_path / "readonly.hmdb"
    connection = sqlite3.connect(hm3_path)
    connection.execute("CREATE TABLE handhistories (handhistory_id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    hm3_path.chmod(0o444)

    state_connection = connect_state_db(tmp_path / "coach.sqlite")
    try:
        state_connection.execute(
            """
            INSERT INTO training_runs (created_at, database_name, hero_name)
            VALUES ('2026-05-24T12:00:00Z', 'x.hmdb', 'hero')
            """
        )
        state_connection.commit()
    finally:
        state_connection.close()

    hm3_connection = sqlite3.connect(f"file:{hm3_path}?mode=ro", uri=True)
    try:
        try:
            hm3_connection.execute("CREATE TABLE should_fail (id INTEGER)")
            write_failed = False
        except sqlite3.OperationalError:
            write_failed = True
    finally:
        hm3_connection.close()

    assert write_failed is True
