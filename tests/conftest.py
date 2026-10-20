import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tanks_list():
    return json.loads((FIXTURES / "tanks_list.json").read_text())


@pytest.fixture
def graph_data():
    return json.loads((FIXTURES / "graph_data.json").read_text())
