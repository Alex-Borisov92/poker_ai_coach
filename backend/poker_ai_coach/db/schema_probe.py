import sqlite3

EXPECTED_TABLES = [
    "handhistories",
    "tournaments",
    "tournament_players",
    "players",
    "imported_files",
    "import_summaries",
    "error_hands",
]


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def list_tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [row["name"] for row in rows]


def count_table_rows(connection: sqlite3.Connection, table_name: str) -> int:
    quoted_name = quote_identifier(table_name)
    row = connection.execute(f"SELECT COUNT(*) AS row_count FROM {quoted_name}").fetchone()
    return int(row["row_count"])


def probe_schema(connection: sqlite3.Connection) -> tuple[list[str], dict[str, int], list[str]]:
    tables = list_tables(connection)
    present_tables = set(tables)
    table_counts = {
        table_name: count_table_rows(connection, table_name)
        for table_name in EXPECTED_TABLES
        if table_name in present_tables
    }
    missing_tables = [
        table_name for table_name in EXPECTED_TABLES if table_name not in present_tables
    ]
    return tables, table_counts, missing_tables
