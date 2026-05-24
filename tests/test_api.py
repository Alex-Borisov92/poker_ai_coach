import sqlite3

from fastapi.testclient import TestClient
from poker_ai_coach.config import clear_runtime_hm3_db_path
from poker_ai_coach.main import app


def create_fixture_db(database_path):
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY, playername TEXT)")
    connection.execute("CREATE TABLE handhistories (handhistory_id INTEGER PRIMARY KEY)")
    connection.execute("INSERT INTO players (playername) VALUES ('hero_test')")
    connection.commit()
    connection.close()


def test_health_endpoint(monkeypatch):
    monkeypatch.delenv("HM3_DB_PATH", raising=False)
    monkeypatch.setenv("HERO_NAME", "surok_valera")
    monkeypatch.setenv("AI_ENABLED", "false")
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["hero_name"] == "surok_valera"
    assert data["ai_enabled"] is False


def test_database_status_without_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HM3_DB_PATH", raising=False)
    client = TestClient(app)

    response = client.get("/api/database/status")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is False
    assert data["connected"] is False
    assert data["database_name"] is None
    assert any(warning.startswith("HM3_DB_PATH is not configured.") for warning in data["warnings"])


def test_database_status_with_fixture_db(monkeypatch, tmp_path):
    database_path = tmp_path / "tiny.hmdb"
    create_fixture_db(database_path)
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    client = TestClient(app)

    response = client.get("/api/database/status")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["connected"] is True
    assert data["database_name"] == "tiny.hmdb"
    assert "players" in data["tables"]
    assert data["table_counts"]["players"] == 1
    assert data["table_counts"]["handhistories"] == 0
    assert "tournament_players" in data["missing_tables"]
    assert any(warning.startswith("Missing expected HM3 tables:") for warning in data["warnings"])


def test_database_status_with_missing_file(monkeypatch, tmp_path):
    database_path = tmp_path / "missing.hmdb"
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    client = TestClient(app)

    response = client.get("/api/database/status")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["connected"] is False
    assert data["database_name"] == "missing.hmdb"
    assert "Database file was not found: missing.hmdb" == data["error"]
    assert "file that does not exist" in data["warnings"][0]


def test_database_status_with_wrong_file(monkeypatch, tmp_path):
    database_path = tmp_path / "notes.txt"
    database_path.write_text("not sqlite", encoding="utf-8")
    monkeypatch.setenv("HM3_DB_PATH", str(database_path))
    client = TestClient(app)

    response = client.get("/api/database/status")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["connected"] is False
    assert data["database_name"] == "notes.txt"
    assert data["error"] == "Wrong database file type: notes.txt"
    assert "Configured file does not look like an HM3 .hmdb file." in data["warnings"]
    assert (
        "Configured file is not a SQLite database. Select the HM3 .hmdb file." in data["warnings"]
    )


def test_set_database_path_loads_fixture_for_current_session(monkeypatch, tmp_path):
    clear_runtime_hm3_db_path()
    monkeypatch.delenv("HM3_DB_PATH", raising=False)
    database_path = tmp_path / "runtime.hmdb"
    create_fixture_db(database_path)
    client = TestClient(app)

    response = client.post("/api/database/path", json={"database_path": str(database_path)})

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["connected"] is True
    assert data["database_name"] == "runtime.hmdb"
    assert "Database path was loaded for this backend session only." in data["warnings"]

    status_response = client.get("/api/database/status")
    status_data = status_response.json()
    assert status_data["connected"] is True
    assert status_data["database_name"] == "runtime.hmdb"
    clear_runtime_hm3_db_path()


def test_set_database_path_rejects_wrong_file(tmp_path):
    clear_runtime_hm3_db_path()
    database_path = tmp_path / "wrong.txt"
    database_path.write_text("not sqlite", encoding="utf-8")
    client = TestClient(app)

    response = client.post("/api/database/path", json={"database_path": str(database_path)})

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert data["error"] == "Wrong database file type: wrong.txt"
    clear_runtime_hm3_db_path()
