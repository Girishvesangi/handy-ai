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

    topics = [t for t, _ in agent.room.local_participant.sent]
    assert topics and set(topics) == {"handy.state"}
    last_state = agent.room.local_participant.sent[-1][1]
    assert last_state["guide"]["id"] == 1001


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
