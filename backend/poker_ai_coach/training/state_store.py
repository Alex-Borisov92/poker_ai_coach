import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from poker_ai_coach.models.training import (
    TrainingCompareResponse,
    TrainingLeak,
    TrainingRunCreateResponse,
    TrainingRunDetail,
    TrainingRunList,
    TrainingRunSummary,
    TrainingStudyItem,
)

STATE_DB_PATH = Path("local_state") / "coach.sqlite"


def connect_state_db(path: Path = STATE_DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    ensure_schema(connection)
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS training_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            database_name TEXT,
            hero_name TEXT NOT NULL,
            model TEXT,
            total_hands INTEGER NOT NULL DEFAULT 0,
            valid_hand_count INTEGER NOT NULL DEFAULT 0,
            invalid_1970_count INTEGER NOT NULL DEFAULT 0,
            max_hand_id INTEGER,
            latest_valid_month TEXT,
            initial_summary TEXT NOT NULL DEFAULT '',
            deep_leak_result TEXT NOT NULL DEFAULT '',
            study_plan_result TEXT NOT NULL DEFAULT '',
            warnings_json TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS training_leaks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_run_id INTEGER NOT NULL,
            leak_key TEXT NOT NULL,
            title TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            evidence TEXT NOT NULL,
            coach_read TEXT NOT NULL,
            sample_size INTEGER NOT NULL DEFAULT 0,
            related_hand_ids_json TEXT NOT NULL DEFAULT '[]',
            confidence TEXT NOT NULL DEFAULT 'medium',
            FOREIGN KEY(training_run_id) REFERENCES training_runs(id)
        );

        CREATE TABLE IF NOT EXISTS training_study_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_run_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            drill TEXT NOT NULL,
            checklist_json TEXT NOT NULL DEFAULT '[]',
            linked_leak_keys_json TEXT NOT NULL DEFAULT '[]',
            linked_hand_ids_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'open',
            FOREIGN KEY(training_run_id) REFERENCES training_runs(id)
        );

        CREATE TABLE IF NOT EXISTS training_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_run_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY(training_run_id) REFERENCES training_runs(id)
        );
        """
    )
    connection.commit()


def create_training_run(
    *,
    database_name: str | None,
    hero_name: str,
    model: str | None,
    total_hands: int,
    valid_hand_count: int,
    invalid_1970_count: int,
    max_hand_id: int | None,
    latest_valid_month: str | None,
    initial_summary: str,
    warnings: list[str],
    leaks: list[TrainingLeak],
    study_items: list[TrainingStudyItem],
    path: Path = STATE_DB_PATH,
) -> TrainingRunCreateResponse:
    with connect_state_db(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO training_runs (
                created_at, database_name, hero_name, model, total_hands,
                valid_hand_count, invalid_1970_count, max_hand_id, latest_valid_month,
                initial_summary, warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now(),
                database_name,
                hero_name,
                model,
                total_hands,
                valid_hand_count,
                invalid_1970_count,
                max_hand_id,
                latest_valid_month,
                initial_summary,
                dump_json(warnings),
            ),
        )
        training_run_id = int(cursor.lastrowid)
        for leak in leaks:
            insert_leak(connection, training_run_id, leak)
        for item in study_items:
            insert_study_item(connection, training_run_id, item)
        connection.commit()
    detail = get_training_run(training_run_id, path=path)
    return TrainingRunCreateResponse(created=True, training_run=detail)


def list_training_runs(path: Path = STATE_DB_PATH) -> TrainingRunList:
    with connect_state_db(path) as connection:
        rows = connection.execute(
            """
            SELECT tr.*,
                   COUNT(DISTINCT tl.id) leak_count,
                   COUNT(DISTINCT tsi.id) study_item_count
            FROM training_runs tr
            LEFT JOIN training_leaks tl ON tl.training_run_id = tr.id
            LEFT JOIN training_study_items tsi ON tsi.training_run_id = tr.id
            GROUP BY tr.id
            ORDER BY tr.id DESC
            """
        ).fetchall()
    return TrainingRunList(training_runs=[summary_from_row(row) for row in rows])


def get_training_run(training_run_id: int, path: Path = STATE_DB_PATH) -> TrainingRunDetail | None:
    with connect_state_db(path) as connection:
        row = connection.execute(
            """
            SELECT tr.*,
                   COUNT(DISTINCT tl.id) leak_count,
                   COUNT(DISTINCT tsi.id) study_item_count
            FROM training_runs tr
            LEFT JOIN training_leaks tl ON tl.training_run_id = tr.id
            LEFT JOIN training_study_items tsi ON tsi.training_run_id = tr.id
            WHERE tr.id = ?
            GROUP BY tr.id
            """,
            (training_run_id,),
        ).fetchone()
        if row is None:
            return None
        leaks = [
            leak_from_row(leak_row)
            for leak_row in connection.execute(
                "SELECT * FROM training_leaks WHERE training_run_id = ? ORDER BY id",
                (training_run_id,),
            ).fetchall()
        ]
        study_items = [
            study_item_from_row(item_row)
            for item_row in connection.execute(
                "SELECT * FROM training_study_items WHERE training_run_id = ? ORDER BY id",
                (training_run_id,),
            ).fetchall()
        ]
    summary = summary_from_row(row)
    return TrainingRunDetail(
        **summary.model_dump(),
        valid_hand_count=int(row["valid_hand_count"] or 0),
        invalid_1970_count=int(row["invalid_1970_count"] or 0),
        warnings=load_json(row["warnings_json"]),
        leaks=leaks,
        study_items=study_items,
        deep_leak_result=str(row["deep_leak_result"] or ""),
        study_plan_result=str(row["study_plan_result"] or ""),
    )


def compare_latest_training_run(
    training_run_id: int,
    path: Path = STATE_DB_PATH,
) -> TrainingCompareResponse:
    with connect_state_db(path) as connection:
        current = connection.execute(
            "SELECT * FROM training_runs WHERE id = ?", (training_run_id,)
        ).fetchone()
        if current is None:
            return TrainingCompareResponse(
                training_run_id=training_run_id,
                error="Training run not found.",
            )
        previous = connection.execute(
            """
            SELECT * FROM training_runs
            WHERE id < ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (training_run_id,),
        ).fetchone()
    if previous is None:
        return TrainingCompareResponse(
            training_run_id=training_run_id,
            warnings=["No previous training run to compare."],
        )

    current_max = current["max_hand_id"] or 0
    previous_max = previous["max_hand_id"] or 0
    new_hands = max(0, int(current_max) - int(previous_max))
    return TrainingCompareResponse(
        training_run_id=training_run_id,
        previous_training_run_id=int(previous["id"]),
        new_hands=new_hands,
        leak_changes=["Existing leaks remain open until a deep follow-up run updates them."],
        study_plan_changes=["Study plan should be adjusted after reviewing new hands."],
    )


def save_training_text(
    training_run_id: int,
    *,
    deep_leak_result: str | None = None,
    study_plan_result: str | None = None,
    path: Path = STATE_DB_PATH,
) -> None:
    assignments = []
    values: list[Any] = []
    if deep_leak_result is not None:
        assignments.append("deep_leak_result = ?")
        values.append(deep_leak_result)
    if study_plan_result is not None:
        assignments.append("study_plan_result = ?")
        values.append(study_plan_result)
    if not assignments:
        return
    values.append(training_run_id)
    with connect_state_db(path) as connection:
        connection.execute(
            f"UPDATE training_runs SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
        connection.commit()


def insert_leak(
    connection: sqlite3.Connection,
    training_run_id: int,
    leak: TrainingLeak,
) -> None:
    connection.execute(
        """
        INSERT INTO training_leaks (
            training_run_id, leak_key, title, severity, status, evidence,
            coach_read, sample_size, related_hand_ids_json, confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            training_run_id,
            leak.leak_key,
            leak.title,
            leak.severity,
            leak.status,
            leak.evidence,
            leak.coach_read,
            leak.sample_size,
            dump_json(leak.related_hand_ids),
            leak.confidence,
        ),
    )


def insert_study_item(
    connection: sqlite3.Connection,
    training_run_id: int,
    item: TrainingStudyItem,
) -> None:
    connection.execute(
        """
        INSERT INTO training_study_items (
            training_run_id, title, drill, checklist_json, linked_leak_keys_json,
            linked_hand_ids_json, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            training_run_id,
            item.title,
            item.drill,
            dump_json(item.checklist),
            dump_json(item.linked_leak_keys),
            dump_json(item.linked_hand_ids),
            item.status,
        ),
    )


def summary_from_row(row: sqlite3.Row) -> TrainingRunSummary:
    return TrainingRunSummary(
        id=int(row["id"]),
        created_at=str(row["created_at"]),
        database_name=row["database_name"],
        hero_name=str(row["hero_name"]),
        model=row["model"],
        total_hands=int(row["total_hands"] or 0),
        max_hand_id=row["max_hand_id"],
        latest_valid_month=row["latest_valid_month"],
        initial_summary=str(row["initial_summary"] or ""),
        leak_count=int(row["leak_count"] or 0),
        study_item_count=int(row["study_item_count"] or 0),
    )


def leak_from_row(row: sqlite3.Row) -> TrainingLeak:
    return TrainingLeak(
        id=int(row["id"]),
        training_run_id=int(row["training_run_id"]),
        leak_key=str(row["leak_key"]),
        title=str(row["title"]),
        severity=str(row["severity"]),
        status=str(row["status"]),
        evidence=str(row["evidence"]),
        coach_read=str(row["coach_read"]),
        sample_size=int(row["sample_size"] or 0),
        related_hand_ids=[int(hand_id) for hand_id in load_json(row["related_hand_ids_json"])],
        confidence=str(row["confidence"]),
    )


def study_item_from_row(row: sqlite3.Row) -> TrainingStudyItem:
    return TrainingStudyItem(
        id=int(row["id"]),
        training_run_id=int(row["training_run_id"]),
        title=str(row["title"]),
        drill=str(row["drill"]),
        checklist=[str(item) for item in load_json(row["checklist_json"])],
        linked_leak_keys=[str(item) for item in load_json(row["linked_leak_keys_json"])],
        linked_hand_ids=[int(hand_id) for hand_id in load_json(row["linked_hand_ids_json"])],
        status=str(row["status"]),
    )


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def load_json(value: str | None) -> list[Any]:
    if not value:
        return []
    loaded = json.loads(value)
    return loaded if isinstance(loaded, list) else []
