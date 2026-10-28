"""The step checker: does the camera frame show the current step done right?

The live voice model only glances at frames. For a careful verdict we make a
separate call to a vision model with three inputs: the step's instructions,
iFixit's reference photo for that step, and the user's latest camera frame.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Literal

import aiohttp
from google import genai
from google.genai import types

from .guides import Guide, Step

CHECKER_MODEL = os.getenv("CHECKER_MODEL") or "gemini-3.8-flash"

Verdict = Literal["done", "not_done", "wrong", "unclear"]
VERDICTS: tuple[Verdict, ...] = ("done", "not_done", "wrong", "unclear")

PROMPT = """You check one step of a laptop repair from a phone camera photo.

Guide: {guide_title}
Step {number} of {total}: {step_title}
Instructions: {instructions}

You get up to two images. If there are two, the FIRST is iFixit's reference
photo for this step and the SECOND is the user's camera right now. If there is
one, it is the user's camera.

Decide one verdict:
- "done": the camera shows the result this step asks for.
- "not_done": the step has not been finished yet, but nothing is wrong.
- "wrong": the user did something this step warns against, or a different
  part is being worked on, or something looks damaged or unsafe.
- "unclear": the photo is too blurry, dark, far, or the part is not in view.

Be strict about "done" and only use "wrong" when you can see the problem.
Give a short reason (under 20 words) about what you see, and a short spoken
tip for the user (under 20 words)."""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
        "tip": {"type": "string"},
    },
    "required": ["verdict", "confidence", "reason", "tip"],
}


@dataclass
class CheckResult:
    verdict: Verdict
    confidence: float
    reason: str
    tip: str
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def parse_result(text: str, latency_ms: int = 0) -> CheckResult:
    """Parse the model's JSON. Anything malformed becomes "unclear" rather than crashing."""
    try:
        data = json.loads(text)
        verdict = data.get("verdict")
        if verdict not in VERDICTS:
            raise ValueError(verdict)
        confidence = min(max(float(data.get("confidence", 0.0)), 0.0), 1.0)
        return CheckResult(verdict, confidence, str(data.get("reason", "")), str(data.get("tip", "")), latency_ms)
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError):
        return CheckResult("unclear", 0.0, "Could not read the checker's answer.", "Try checking again.", latency_ms)


def build_prompt(guide: Guide, step: Step) -> str:
    return PROMPT.format(
        guide_title=guide.title,
        number=step.number,
        total=len(guide.steps),
        step_title=step.title or "(untitled)",
        instructions=step.text or "(see the reference photo)",
    )


class StepChecker:
    def __init__(self, client: genai.Client | None = None, model: str = CHECKER_MODEL) -> None:
        self._client = client or genai.Client()
        self._model = model
        self._ref_cache: dict[str, tuple[bytes, str]] = {}

    async def _reference_image(self, url: str) -> tuple[bytes, str] | None:
        """Download (and cache) a reference photo. Returns (bytes, mime type)."""
        if url in self._ref_cache:
            return self._ref_cache[url]
        try:
            async with aiohttp.ClientSession() as http:
                async with http.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    resp.raise_for_status()
                    mime = resp.content_type if resp.content_type.startswith("image/") else "image/jpeg"
                    image = (await resp.read(), mime)
        except (aiohttp.ClientError, TimeoutError):
            return None  # check without the reference rather than fail
        self._ref_cache[url] = image
        return image

    async def check(
        self, guide: Guide, step: Step, frame_jpeg: bytes, use_reference: bool = True
    ) -> CheckResult:
        parts: list[types.Part | str] = [build_prompt(guide, step)]
        if use_reference and step.image_urls:
            ref = await self._reference_image(step.image_urls[0])
            if ref:
                parts.append(types.Part.from_bytes(data=ref[0], mime_type=ref[1]))
        parts.append(types.Part.from_bytes(data=frame_jpeg, mime_type="image/jpeg"))

        start = time.perf_counter()
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=RESPONSE_SCHEMA,
                temperature=0.0,
            ),
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return parse_result(resp.text or "", latency_ms)


# ---- Pointer: where on the camera image should the user act next? --------

LOCATE_PROMPT = """You help someone repairing a laptop by pointing at the part
they need to work on for this step, in a photo from their phone camera.

Guide: {guide_title}
Step {number}: {step_title}
Instructions: {instructions}

Find the single part the user should touch or look at for this step (for
example a screw, connector, cable, battery, RAM stick). If it is visible,
return its bounding box as box_2d = [ymin, xmin, ymax, xmax], with each value
normalized to 0-1000, and a short label of 1 to 4 words. If it is not visible,
set found to false."""

LOCATE_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "label": {"type": "string"},
        "box_2d": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["found", "label"],
}


@dataclass
class Pointer:
    found: bool
    label: str
    box: list[float]  # [ymin, xmin, ymax, xmax] as fractions 0-1 of the image
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def parse_pointer(text: str, latency_ms: int = 0) -> Pointer:
    """Turn the model's 0-1000 box into 0-1 fractions; anything odd means "not found"."""
    try:
        data = json.loads(text)
        box = data.get("box_2d") or []
        if not data.get("found") or len(box) != 4:
            return Pointer(False, str(data.get("label", "")), [], latency_ms)
        ymin, xmin, ymax, xmax = (min(max(float(v), 0.0), 1000.0) / 1000 for v in box)
        if ymax <= ymin or xmax <= xmin:
            return Pointer(False, str(data.get("label", "")), [], latency_ms)
        return Pointer(True, str(data.get("label", "")), [ymin, xmin, ymax, xmax], latency_ms)
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError):
        return Pointer(False, "", [], latency_ms)


async def locate_part(checker: StepChecker, guide: Guide, step: Step, frame_jpeg: bytes) -> Pointer:
    prompt = LOCATE_PROMPT.format(
        guide_title=guide.title,
        number=step.number,
        step_title=step.title or "(untitled)",
        instructions=step.text or "(no text)",
    )
    start = time.perf_counter()
    resp = await checker._client.aio.models.generate_content(
        model=checker._model,
        contents=[prompt, types.Part.from_bytes(data=frame_jpeg, mime_type="image/jpeg")],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=LOCATE_SCHEMA,
            temperature=0.0,
        ),
    )
    return parse_pointer(resp.text or "", int((time.perf_counter() - start) * 1000))
