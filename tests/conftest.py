"""
Session-scoped fixtures shared across the test suite.
"""

import pytest

from sandbox.seed import seed


@pytest.fixture(scope="session", autouse=True)
def seeded_sandbox():
    """Ensure sandbox/postings/ is populated before any test runs."""
    seed()
