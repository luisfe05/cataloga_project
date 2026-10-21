"""pytest fixtures shared across all test modules.

Provides:
- a Flask test client backed by a temporary SQLite database, so tests
  never touch the real database/catalog.db
"""

import pytest
from backend.app import create_app


@pytest.fixture
def flask_client(tmp_path):
    """Return a Flask test client that uses a temporary database.

    tmp_path is a built-in pytest fixture: a fresh folder for each test
    that pytest deletes on its own, so every test starts with an empty
    database.
    """
    app = create_app(db_path=str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
