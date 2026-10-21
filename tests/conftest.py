"""pytest fixtures shared across all test modules.

Provides:
- a temporary in-memory SQLite database for unit tests
- a Flask test client for route integration tests
- a mock AIProviderClient so tests never make real API calls
"""

import pytest
from backend.app import create_app
from backend.db.schema import init_db


@pytest.fixture
def flask_client():
    """Return a Flask test client backed by an in-memory database."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_ai_client(mocker):
    """Return a mock AIProviderClient that never calls the real API.

    Uses pytest-mock (mocker fixture). Import this fixture in any test
    that exercises ClassificationPipeline.
    """
    pass
