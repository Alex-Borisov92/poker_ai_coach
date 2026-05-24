import sqlite3
from pathlib import Path

SQLITE_HEADER = b"SQLite format 3\x00"


def missing_database_path_warning() -> str:
    return "HM3_DB_PATH is not configured. Set it in .env to your local HM3 .hmdb file."


def missing_tables_warning(missing_tables: list[str]) -> str:
    table_list = ", ".join(missing_tables)
    return f"Missing expected HM3 tables: {table_list}."


def database_open_failure(database_path: Path, exc: Exception) -> tuple[list[str], str]:
    database_name = Path(database_path).name
    warnings = []

    if not database_path.exists():
        return (
            ["HM3_DB_PATH points to a file that does not exist. Check .env and the file name."],
            f"Database file was not found: {database_name}",
        )

    if not database_path.is_file():
        return (
            ["HM3_DB_PATH must point to a single HM3 .hmdb file, not a folder."],
            f"Configured database path is not a file: {database_name}",
        )

    if database_path.suffix.lower() != ".hmdb":
        warnings.append("Configured file does not look like an HM3 .hmdb file.")

    if _looks_like_wrong_sqlite_file(database_path):
        warnings.append("Configured file is not a SQLite database. Select the HM3 .hmdb file.")
        return warnings, f"Wrong database file type: {database_name}"

    if _is_locked_error(exc):
        warnings.append("Database is locked or busy. Close HM3 import or maintenance and retry.")
        return warnings, "SQLite database is locked or busy."

    warnings.append(
        "Database could not be opened in read-only mode. Check that the file is a valid HM3 DB."
    )
    return warnings, str(exc)


def _looks_like_wrong_sqlite_file(database_path: Path) -> bool:
    try:
        with database_path.open("rb") as handle:
            header = handle.read(len(SQLITE_HEADER))
    except OSError:
        return False
    return bool(header and header != SQLITE_HEADER)


def _is_locked_error(exc: Exception) -> bool:
    if isinstance(exc, sqlite3.OperationalError):
        message = str(exc).lower()
        return "locked" in message or "busy" in message
    return False
