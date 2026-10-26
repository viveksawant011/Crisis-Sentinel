"""Seeds a clean demo database before the test session and restores it afterwards."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import reset_demo_state  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _seeded_database():
    assert reset_demo_state()["success"]
    yield
    reset_demo_state()


@pytest.fixture()
def fresh_db():
    assert reset_demo_state()["success"]
    yield
    reset_demo_state()
