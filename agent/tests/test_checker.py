import json
from types import SimpleNamespace

import pytest

from handy.checker import StepChecker, build_prompt, parse_result


def test_parse_valid_result():
    r = parse_result(json.dumps({"verdict": "wrong", "confidence": 1.4, "reason": "r", "tip": "t"}), 120)
    assert r.verdict == "wrong"
    assert r.confidence == 1.0  # clamped
    assert r.latency_ms == 120


@pytest.mark.parametrize("text", ["", "not json", json.dumps({"verdict": "maybe"}), json.dumps([1, 2])])
def test_parse_bad_result_is_unclear(text):
    assert parse_result(text).verdict == "unclear"


def test_prompt_contains_step(guides):
    prompt = build_prompt(guides[0], guides[0].steps[1])
    assert "Step 2 of 3" in prompt
    assert "Disconnect the internal battery connector" in prompt


class FakeModels:
    def __init__(self, reply: dict):
        self.reply = reply
        self.calls = []

    async def generate_content(self, model, contents, config):
        self.calls.append(contents)
        return SimpleNamespace(text=json.dumps(self.reply))


@pytest.mark.asyncio
async def test_check_sends_reference_and_frame(guides):
    models = FakeModels({"verdict": "done", "confidence": 0.9, "reason": "Cover is off.", "tip": "Next step."})
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    checker = StepChecker(client=client, model="test")

    async def fake_ref(url):
        return (b"ref", "image/jpeg")

    checker._reference_image = fake_ref
    result = await checker.check(guides[0], guides[0].steps[0], b"frame")
    assert result.verdict == "done"
    assert len(models.calls[0]) == 3  # prompt, reference photo, camera frame

    await checker.check(guides[0], guides[0].steps[0], b"frame", use_reference=False)
    assert len(models.calls[1]) == 2
