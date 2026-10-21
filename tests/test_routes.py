"""Integration tests for Flask routes using the test client.

Uses the flask_client fixture from conftest.py.
Tests confirm correct HTTP status codes and response shapes,
not business logic (that belongs in the unit test files).
"""

import pytest


def test_placeholder(flask_client):
    """Remove once real tests are added."""
    pass
