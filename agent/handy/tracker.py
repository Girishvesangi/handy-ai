"""Tracks where the user is inside a repair guide."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .guides import Guide, Step


@dataclass
class StepTracker:
    guide: Guide | None = None
    index: int = 0  # 0-based into guide.steps
    completed: set[int] = field(default_factory=set)  # step numbers the checker or user confirmed
    started_at: float = 0.0
    warnings: list[dict] = field(default_factory=list)  # mistakes the checker caught: {"step", "reason"}
    checks: int = 0

    @property
    def active(self) -> bool:
        return self.guide is not None and bool(self.guide.steps)

    @property
    def current(self) -> Step | None:
        return self.guide.steps[self.index] if self.active else None

    @property
    def is_last(self) -> bool:
        return self.active and self.index == len(self.guide.steps) - 1

    def start(self, guide: Guide) -> Step | None:
        self.guide, self.index, self.completed = guide, 0, set()
        self.started_at, self.warnings, self.checks = time.time(), [], 0
        return self.current

    def record_check(self, verdict: str, reason: str) -> None:
        self.checks += 1
        if verdict == "wrong" and self.current:
            self.warnings.append({"step": self.current.number, "reason": reason})

    def next(self) -> Step | None:
        """Advance one step. Returns None when the guide is finished."""
        if not self.active:
            return None
        self.completed.add(self.current.number)
        if self.is_last:
            return None
        self.index += 1
        return self.current

    def previous(self) -> Step | None:
        if self.active and self.index > 0:
            self.index -= 1
        return self.current

    def go_to(self, number: int) -> Step | None:
        if self.active and 1 <= number <= len(self.guide.steps):
            self.index = number - 1
        return self.current

    def stop(self) -> None:
        self.guide, self.index, self.completed = None, 0, set()
        self.started_at, self.warnings, self.checks = 0.0, [], 0

    def recap(self) -> dict:
        """Summary shown when a guide is finished."""
        if not self.active:
            return {}
        return {
            "guide_id": self.guide.id,
            "title": self.guide.title,
            "url": self.guide.url,
            "total_steps": len(self.guide.steps),
            "steps_completed": len(self.completed),
            "minutes": round((time.time() - self.started_at) / 60, 1) if self.started_at else 0,
            "checks": self.checks,
            "mistakes_caught": self.warnings,
        }

    def state(self) -> dict:
        """What the web app needs to draw the step card."""
        if not self.active:
            return {"guide": None}
        step = self.current
        return {
            "guide": {
                "id": self.guide.id,
                "title": self.guide.title,
                "device": self.guide.device,
                "url": self.guide.url,
                "total_steps": len(self.guide.steps),
                "tools": self.guide.tools,
                "difficulty": self.guide.difficulty,
                "time_required": self.guide.time_required,
            },
            "step": {
                "number": step.number,
                "title": step.title,
                "lines": step.lines,
                "image_urls": step.image_urls,
            },
            "completed": sorted(self.completed),
        }

    def describe_current(self) -> str:
        """Text handed to the voice model so it can read the step aloud."""
        if not self.active:
            return "No guide is active."
        step = self.current
        title = f" ({step.title})" if step.title else ""
        return (
            f"Step {step.number} of {len(self.guide.steps)}{title}: {step.text or 'See the photo.'}"
        )
