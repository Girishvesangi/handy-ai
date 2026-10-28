"""Exercises the agent's tools end to end, with a fake room and fake checker."""

import json
from types import SimpleNamespace

import pytest

from handy.checker import CheckResult
from handy.eventlog import EventLog, read_events
from handy.search import GuideIndex


class FakeParticipant:
    def __init__(self):
        self.sent = []

    async def publish_data(self, payload, *, reliable=True, topic=""):
        self.sent.append((topic, json.loads(payload)))


@pytest.fixture
def agent(guides, tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    import agent as agent_module

    monkeypatch.setattr(agent_module, "POINTER_AUTO", False)  # no background vision calls in tests

    room = SimpleNamespace(on=lambda *a, **k: None, remote_participants={}, local_participant=FakeParticipant())
    a = agent_module.Handy(room, GuideIndex(guides), EventLog("test", tmp_path))
    a.log_dir = tmp_path
    return a


@pytest.mark.asyncio
async def test_find_start_and_walk(agent):
    found = json.loads(await agent.find_guides(None, "thinkpad t480 ram"))
    assert found[0]["guide_id"] == 1001

    started = await agent.start_guide(None, 1001)
    assert "Phillips #1 Screwdriver" in started
    assert "Step 1 of 3" in started

    assert "Step 2 of 3" in await agent.next_step(None)
    assert "Step 1 of 3" in await agent.previous_step(None)
    assert "Step 3 of 3" in await agent.go_to_step(None, 3)
    assert "last step" in await agent.next_step(None)

    sent = agent.room.local_participant.sent
    assert {t for t, _ in sent} == {"handy.state", "handy.recap"}
    recap = sent[-1][1]
    assert sent[-1][0] == "handy.recap"
    assert recap["guide_id"] == 1001 and recap["total_steps"] == 3
    state = [m for t, m in sent if t == "handy.state"][-1]
    assert state["guide"]["tools"] == ["Phillips #1 Screwdriver", "Spudger"]


@pytest.mark.asyncio
async def test_unknown_guide(agent):
    assert "no guide" in (await agent.start_guide(None, 999)).lower()


@pytest.mark.asyncio
async def test_check_publishes_verdict_and_logs(agent):
    await agent.start_guide(None, 1001)
    agent.frames.jpeg = lambda: b"jpeg"

    async def fake_check(guide, step, frame, use_reference=True):
        return CheckResult("done", 0.9, "Cover is off.", "Go to the next step.", 900)

    agent.checker.check = fake_check
    result = json.loads(await agent.check_my_work(None))
    assert result["verdict"] == "done"
    assert 1 in agent.tracker.completed

    sent = agent.room.local_participant.sent
    assert ("handy.check", {**result, "step": 1}) in sent
    events = read_events(agent.log_dir)
    assert any(e["event"] == "check" and e["verdict"] == "done" for e in events)


@pytest.mark.asyncio
async def test_check_without_camera(agent):
    await agent.start_guide(None, 1001)
    agent.frames.jpeg = lambda: None
    result = json.loads(await agent.check_my_work(None))
    assert result["verdict"] == "unclear"


@pytest.mark.asyncio
async def test_check_survives_checker_errors(agent):
    await agent.start_guide(None, 1001)
    agent.frames.jpeg = lambda: b"jpeg"

    async def broken(*a, **k):
        raise RuntimeError("quota")

    agent.checker.check = broken
    result = json.loads(await agent.check_my_work(None))
    assert result["verdict"] == "unclear"


@pytest.mark.asyncio
async def test_point_to_part(agent, monkeypatch):
    import agent as agent_module
    from handy.checker import Pointer

    assert await agent.point_to_part(None) == "No guide is active."
    await agent.start_guide(None, 1001)
    agent.frames.jpeg = lambda: b"jpeg"
    agent.frames.size = lambda: (720, 1280)

    async def fake_locate(checker, guide, step, frame):
        return Pointer(True, "battery connector", [0.1, 0.2, 0.3, 0.4], 500)

    monkeypatch.setattr(agent_module, "locate_part", fake_locate)
    reply = await agent.point_to_part(None)
    assert "battery connector" in reply
    topic, msg = agent.room.local_participant.sent[-1]
    assert topic == "handy.pointer"
    assert msg["box"] == [0.1, 0.2, 0.3, 0.4] and msg["frame_w"] == 720 and msg["step"] == 1


@pytest.mark.asyncio
async def test_mistakes_show_up_in_recap(agent):
    await agent.start_guide(None, 1001)
    agent.frames.jpeg = lambda: b"jpeg"

    async def wrong(guide, step, frame, use_reference=True):
        return CheckResult("wrong", 0.9, "Ribbon cable lifted first.", "Unplug the battery first.", 800)

    agent.checker.check = wrong
    await agent.check_my_work(None)
    recap = agent.tracker.recap()
    assert recap["checks"] == 1
    assert recap["mistakes_caught"] == [{"step": 1, "reason": "Ribbon cable lifted first."}]
