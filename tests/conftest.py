from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "receipts"


@pytest.fixture
def costco_text() -> str:
    return (FIXTURES / "costco" / "sample1.txt").read_text()


@pytest.fixture
def walmart_text() -> str:
    return (FIXTURES / "walmart" / "sample1.txt").read_text()


@pytest.fixture
def aldi_text() -> str:
    return (FIXTURES / "aldi" / "sample1.txt").read_text()
