"""Step-check eval: how often does the checker give the right verdict?

Two ways to get test cases:

1. Real cases (the ones that matter). Take photos with your phone while
   doing real steps, save them under data/images/, and list them in
   data/step_cases.jsonl:
     {"guide_id": 12345, "step": 3, "image": "images/battery-unplugged.jpg", "label": "done"}
   Labels: done, not_done, wrong, unclear. See data/README.md.

2. A proxy set built from iFixit's own photos (--proxy). For a step, the
   photo from that same step is treated as "done" and a photo from a
   random step of a different guide is treated as "not done". This only
   tests whether the checker can match a photo to its instructions, so
   report it as a proxy, never as real-world accuracy.
"""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path

import aiohttp

from handy.checker import StepChecker
from handy.guides import Guide, load_guides

from .metrics import classification_report, percentile

DATA = Path(__file__).parent / "data"
CLASSES = ["done", "not_done", "wrong", "unclear"]


def load_cases(path: Path = DATA / "step_cases.jsonl") -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_proxy_cases(guides: list[Guide], n: int, seed: int = 7) -> list[dict]:
    """Half positives (a step's own photo), half negatives (another guide's photo)."""
    rng = random.Random(seed)
    steps = [(g, s) for g in guides for s in g.steps if s.image_urls]
    rng.shuffle(steps)
    cases = []
    for i, (g, s) in enumerate(steps[:n]):
        if i % 2 == 0:
            cases.append({"guide_id": g.id, "step": s.number, "image_url": s.image_urls[0], "label": "done"})
        else:
            other_g, other_s = rng.choice([(og, os_) for og, os_ in steps if og.id != g.id])
            cases.append(
                {"guide_id": g.id, "step": s.number, "image_url": other_s.image_urls[0], "label": "not_done"}
            )
    return cases


async def _image_bytes(case: dict, http: aiohttp.ClientSession) -> bytes:
    if "image" in case:
        return (DATA / case["image"]).read_bytes()
    async with http.get(case["image_url"]) as resp:
        resp.raise_for_status()
        return await resp.read()


async def evaluate(cases: list[dict], guides: list[Guide], use_reference: bool, binary: bool) -> dict:
    by_id = {g.id: g for g in guides}
    checker = StepChecker()
    labels, preds, latencies, rows = [], [], [], []
    async with aiohttp.ClientSession() as http:
        for case in cases:
            guide = by_id.get(case["guide_id"])
            if guide is None or not (1 <= case["step"] <= len(guide.steps)):
                continue
            step = guide.steps[case["step"] - 1]
            frame = await _image_bytes(case, http)
            result = await checker.check(guide, step, frame, use_reference=use_reference)
            pred = result.verdict
            label = case["label"]
            if binary:  # proxy set only distinguishes done vs everything else
                pred = "done" if pred == "done" else "not_done"
            labels.append(label)
            preds.append(pred)
            latencies.append(result.latency_ms)
            rows.append({**case, "pred": result.verdict, "reason": result.reason})
    classes = ["done", "not_done"] if binary else CLASSES
    report = classification_report(labels, preds, classes)
    report["latency_ms"] = {"p50": percentile(latencies, 50), "p95": percentile(latencies, 95)}
    report["errors"] = [r for r in rows if (r["pred"] == "done") != (r["label"] == "done")][:20]
    return report


def run(proxy: int = 0, compare_reference: bool = True) -> dict:
    guides = load_guides()
    if not guides:
        raise SystemExit("No guides found. Run `python -m handy.ingest` first.")
    out: dict = {}
    real = load_cases()
    if real:
        out["real"] = asyncio.run(evaluate(real, guides, use_reference=True, binary=False))
    if proxy:
        cases = build_proxy_cases(guides, proxy)
        # The proxy frame IS a reference photo, so never also pass the reference.
        out["proxy"] = asyncio.run(evaluate(cases, guides, use_reference=False, binary=True))
    if real and compare_reference:
        out["real_without_reference"] = asyncio.run(evaluate(real, guides, use_reference=False, binary=False))
    if not out:
        raise SystemExit("No cases. Add data/step_cases.jsonl or pass --proxy 40.")
    return out
