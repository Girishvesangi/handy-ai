"""Repair guide data model and the JSON file that stores guides on disk."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_GUIDES_PATH = Path(__file__).resolve().parent.parent / "data" / "guides.json"


@dataclass
class Step:
    number: int  # 1-based, as shown to the user
    title: str
    lines: list[str]
    image_urls: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(self.lines)


@dataclass
class Guide:
    id: int
    title: str
    device: str  # e.g. "MacBook Air 13\" Early 2015"
    url: str
    difficulty: str = ""
    time_required: str = ""
    introduction: str = ""
    tools: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    # Filled in by `python -m handy.ingest --embed`. Empty means keyword search only.
    embedding: list[float] = field(default_factory=list)

    def search_text(self) -> str:
        """Text indexed for search: title and device matter most, so repeat them."""
        step_titles = " ".join(s.title for s in self.steps if s.title)
        return f"{self.title} {self.title} {self.device} {self.device} {self.introduction} {step_titles}"

    def summary(self) -> dict:
        """Short form handed to the model when listing search results."""
        return {
            "guide_id": self.id,
            "title": self.title,
            "device": self.device,
            "steps": len(self.steps),
            "difficulty": self.difficulty,
            "time_required": self.time_required,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Guide:
        steps = [Step(**s) for s in d.get("steps", [])]
        return cls(**{**d, "steps": steps})


def load_guides(path: Path = DEFAULT_GUIDES_PATH) -> list[Guide]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [Guide.from_dict(g) for g in data["guides"]]


def save_guides(guides: list[Guide], path: Path = DEFAULT_GUIDES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "iFixit (https://www.ifixit.com), CC BY-NC-SA",
        "guides": [asdict(g) for g in guides],
    }
    path.write_text(json.dumps(payload, indent=1))
