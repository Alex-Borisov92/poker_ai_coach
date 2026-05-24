import pytest
from poker_ai_coach.config import clear_runtime_hm3_db_path


@pytest.fixture(autouse=True)
def clear_runtime_database_path():
    clear_runtime_hm3_db_path()
    yield
    clear_runtime_hm3_db_path()
