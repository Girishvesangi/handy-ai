"""Append-only JSONL log of what happened in each session.

Every tool call, step change, and check verdict is written here with
timings. The eval and stats scripts read these files later.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


class EventLog:
    def __init__(self, session_id: str, log_dir: Path = DEFAULT_LOG_DIR) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id
        self.path = log_dir / f"{session_id}.jsonl"

    def write(self, event: str, **data) -> None:
        record = {"ts": time.time(), "session": self.session_id, "event": event, **data}
        with self.path.open("a") as f:
            f.write(json.dumps(record) + "\n")


def read_events(log_dir: Path = DEFAULT_LOG_DIR) -> list[dict]:
    events = []
    for path in sorted(log_dir.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events
