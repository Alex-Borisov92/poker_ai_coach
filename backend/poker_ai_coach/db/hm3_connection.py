import sqlite3
from pathlib import Path
from urllib.parse import quote


def build_readonly_uri(database_path: Path) -> str:
    absolute_path = database_path.expanduser().resolve()
    encoded_path = quote(absolute_path.as_posix(), safe="/:")
    return f"file:{encoded_path}?mode=ro"


def connect_readonly(database_path: Path) -> sqlite3.Connection:
    uri = build_readonly_uri(database_path)
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection
