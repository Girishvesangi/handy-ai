import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from handy.guides import Guide, Step  # noqa: E402
from handy.ifixit import parse_guide  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def raw_guide() -> dict:
    return json.loads((FIXTURES / "ifixit_guide.json").read_text())


@pytest.fixture
def guides(raw_guide) -> list[Guide]:
    def make(gid: int, title: str, device: str, n_steps: int = 3) -> Guide:
        steps = [Step(i, f"Step {i}", [f"Do thing {i}."], [f"https://img.example/{gid}-{i}"]) for i in range(1, n_steps + 1)]
        return Guide(gid, title, device, f"https://www.ifixit.com/Guide/{gid}", steps=steps)

    return [
        parse_guide(raw_guide),
        make(2002, "MacBook Air 13\" Early 2015 Battery Replacement", "MacBook Air 13\" Early 2015"),
        make(3003, "Dell XPS 13 9360 SSD Replacement", "Dell XPS 13 9360"),
        make(4004, "MacBook Pro 13\" Retina Fan Replacement", "MacBook Pro 13\" Retina"),
    ]
