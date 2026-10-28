"""Tracks where the user is inside a repair guide."""

from __future__ import annotations

from dataclasses import dataclass, field

from .guides import Guide, Step


@dataclass
class StepTracker:
    guide: Guide | None = None
    index: int = 0  # 0-based into guide.steps
    completed: set[int] = field(default_factory=set)  # step numbers the checker or user confirmed

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
        return self.current

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
