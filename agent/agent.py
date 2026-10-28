"""Handy: a live voice and camera copilot for laptop repairs.

The agent joins a LiveKit room, hears the user, sees their camera, and
talks back through the Gemini Live API. Its tools let it:
  - find the right iFixit repair guide          (find_guides, start_guide)
  - walk through the guide step by step         (next_step, previous_step, ...)
  - check the user's work with a vision model   (check_my_work, plus a background watcher)

The web app sees the current step through data messages on the
"handy.state" and "handy.check" topics, and can press buttons that call
the agent over RPC ("handy.next", "handy.previous", "handy.check").

Run it with:  python -m livekit.agents start agent.py --dev --log-format colored
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    function_tool,
    room_io,
)
from livekit.plugins import google

from handy.checker import CheckResult, Pointer, StepChecker, locate_part
from handy.eventlog import EventLog
from handy.frames import LatestFrame
from handy.guides import load_guides
from handy.search import GuideIndex
from handy.tracing import setup_langfuse
from handy.tracker import StepTracker

load_dotenv()
logger = logging.getLogger("handy")

LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL") or "gemini-3.8-live"
# Seconds between background checks while a step is active. 0 turns the watcher off.
WATCH_INTERVAL_S = float(os.getenv("WATCH_INTERVAL_S") or 8)
# Only interrupt the user when the checker is at least this sure something is wrong.
WARN_CONFIDENCE = float(os.getenv("WARN_CONFIDENCE") or 0.75)
# Automatically point at the part to touch whenever a new step starts (one extra vision call per step).
POINTER_AUTO = (os.getenv("POINTER_AUTO") or "1") not in ("0", "false", "no")

INSTRUCTIONS = """
You are Handy, a friendly, patient laptop repair helper who can see the
user's phone camera. You talk out loud, so keep every reply to one to three
short sentences.

How to help:
1. When the user says what they want to fix, call find_guides with the
   laptop model (if you can see or hear it) and the repair. If you can't tell
   the model, ask them to show the bottom label first.
2. Read out the top matches briefly and ask which one, or pick the clear
   winner and call start_guide.
3. Read each step in your own words. Mention the tools needed when you start.
4. When the user says they're done with a step, or asks "is this right?",
   call check_my_work. If it is done, say so and call next_step. If it is
   wrong, explain how to fix it. If unclear, ask them to hold the camera
   closer or add light.
5. "Back", "repeat", "skip to step 5" map to previous_step, repeat_step,
   go_to_step.
6. "Where is it?", "which one?", "show me" -> call point_to_part. The app
   draws a box around the part on the user's screen.
7. When the last step is done, congratulate them and summarize briefly.

Rules:
- Only describe what you can actually see. Never guess a model number.
- Safety first: before opening a laptop, remind them to shut it down and
  unplug the charger. Warn about swollen batteries and never puncturing them.
- If no guide fits, say so honestly and give general careful advice.
- Speak the same language the user speaks. Guides are in English, so
  translate steps naturally when you read them.
"""


class Handy(Agent):
    def __init__(self, room: rtc.Room, index: GuideIndex, log: EventLog) -> None:
        super().__init__(instructions=INSTRUCTIONS)
        self.room = room
        self.index = index
        self.log = log
        self.tracker = StepTracker()
        self.checker = StepChecker()
        self.frames = LatestFrame(room)
        self._check_lock = asyncio.Lock()
        self._last_warning = ""
        self._locate_task: asyncio.Task | None = None
        self._embedder = None
        if index.has_embeddings:
            from handy.embeddings import Embedder

            self._embedder = Embedder()

    # ---- messages to the web app ------------------------------------------

    async def publish_state(self) -> None:
        payload = json.dumps(self.tracker.state())
        await self.room.local_participant.publish_data(payload, reliable=True, topic="handy.state")

    async def publish_check(self, result: CheckResult, step_number: int) -> None:
        payload = json.dumps({**result.to_dict(), "step": step_number})
        await self.room.local_participant.publish_data(payload, reliable=True, topic="handy.check")

    async def publish_pointer(self, pointer: Pointer, step_number: int, size: tuple[int, int] | None) -> None:
        w, h = size or (0, 0)
        payload = json.dumps({**pointer.to_dict(), "step": step_number, "frame_w": w, "frame_h": h})
        await self.room.local_participant.publish_data(payload, reliable=True, topic="handy.pointer")

    async def publish_recap(self) -> None:
        payload = json.dumps(self.tracker.recap())
        await self.room.local_participant.publish_data(payload, reliable=True, topic="handy.recap")

    # ---- shared actions (used by voice tools and by the UI buttons) -------

    async def run_check(self, source: str) -> CheckResult | None:
        """Grab the newest camera frame and ask the vision model about the current step."""
        step = self.tracker.current
        if step is None:
            return None
        frame = self.frames.jpeg()
        if frame is None:
            return CheckResult("unclear", 0.0, "No camera frame yet.", "Make sure your camera is on.")
        async with self._check_lock:
            try:
                result = await self.checker.check(self.tracker.guide, step, frame)
            except Exception as e:  # network or quota errors should never kill the call
                logger.warning("step check failed: %s", e)
                return CheckResult("unclear", 0.0, "The checker could not be reached.", "Try again in a moment.")
        if result.verdict == "done":
            self.tracker.completed.add(step.number)
        self.tracker.record_check(result.verdict, result.reason)
        self.log.write(
            "check",
            source=source,
            guide_id=self.tracker.guide.id,
            step=step.number,
            **result.to_dict(),
        )
        await self.publish_check(result, step.number)
        await self.publish_state()
        return result

    async def run_locate(self, source: str) -> Pointer | None:
        """Ask the vision model where the part for the current step is, and draw it in the app."""
        step = self.tracker.current
        frame = self.frames.jpeg()
        if step is None or frame is None:
            return None
        try:
            pointer = await locate_part(self.checker, self.tracker.guide, step, frame)
        except Exception as e:
            logger.warning("locate failed: %s", e)
            return None
        if self.tracker.current is not step:
            return None  # the user moved on while we were looking
        self.log.write("locate", source=source, step=step.number, **pointer.to_dict())
        await self.publish_pointer(pointer, step.number, self.frames.size())
        return pointer

    def auto_locate(self) -> None:
        """Point at the new step's part in the background, without delaying the voice."""
        if not POINTER_AUTO:
            return
        if self._locate_task and not self._locate_task.done():
            self._locate_task.cancel()
        self._locate_task = asyncio.create_task(self.run_locate("auto"))

    async def move(self, action: str, number: int | None = None) -> str:
        before = self.tracker.current.number if self.tracker.current else None
        if action == "next":
            step = self.tracker.next()
            if step is None and self.tracker.active:
                recap = self.tracker.recap()
                self.log.write("guide_finished", **recap)
                await self.publish_state()
                await self.publish_recap()
                caught = len(recap["mistakes_caught"])
                return (
                    f"That was the last step. The repair is complete: {recap['steps_completed']} of "
                    f"{recap['total_steps']} steps confirmed in {recap['minutes']} minutes, "
                    f"{caught} mistake{'s' if caught != 1 else ''} caught along the way."
                )
        elif action == "previous":
            self.tracker.previous()
        elif action == "goto" and number is not None:
            self.tracker.go_to(number)
        self._last_warning = ""
        after = self.tracker.current.number if self.tracker.current else None
        self.log.write("step", action=action, before=before, after=after)
        await self.publish_state()
        if after is not None and after != before:
            self.auto_locate()
        return self.tracker.describe_current()

    # ---- voice tools ------------------------------------------------------

    @function_tool()
    async def find_guides(self, context: RunContext, query: str) -> str:
        """Search the iFixit repair guides. Call this when the user says what they want to fix.

        Args:
            query: The laptop model if known plus the repair, e.g. "MacBook Air 2015 battery replacement".
        """
        start = time.perf_counter()
        vec = None
        if self._embedder:
            try:
                vec = await self._embedder.embed_query(query)
            except Exception as e:
                logger.warning("query embedding failed, using keyword search only: %s", e)
        results = self.index.search(query, query_vec=vec, k=3)
        self.log.write(
            "search",
            query=query,
            results=[g.id for g in results],
            hybrid=vec is not None,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )
        if not results:
            return "No matching guides found."
        return json.dumps([g.summary() for g in results])

    @function_tool()
    async def start_guide(self, context: RunContext, guide_id: int) -> str:
        """Start walking the user through a guide from step 1.

        Args:
            guide_id: The guide_id from find_guides.
        """
        guide = self.index.by_id(guide_id)
        if guide is None:
            return f"There is no guide with id {guide_id}. Call find_guides first."
        self.tracker.start(guide)
        self._last_warning = ""
        self.log.write("guide_started", guide_id=guide.id, title=guide.title)
        await self.publish_state()
        self.auto_locate()
        tools = ", ".join(guide.tools) if guide.tools else "not listed"
        return (
            f"Started '{guide.title}' ({len(guide.steps)} steps, difficulty {guide.difficulty or 'unknown'}). "
            f"Tools needed: {tools}. {self.tracker.describe_current()}"
        )

    @function_tool()
    async def next_step(self, context: RunContext) -> str:
        """Move to the next step of the active guide."""
        return await self.move("next")

    @function_tool()
    async def previous_step(self, context: RunContext) -> str:
        """Go back one step."""
        return await self.move("previous")

    @function_tool()
    async def repeat_step(self, context: RunContext) -> str:
        """Get the current step again, to repeat it to the user."""
        return self.tracker.describe_current()

    @function_tool()
    async def go_to_step(self, context: RunContext, number: int) -> str:
        """Jump to a specific step number.

        Args:
            number: The 1-based step number.
        """
        return await self.move("goto", number)

    @function_tool()
    async def check_my_work(self, context: RunContext) -> str:
        """Look closely at the camera and judge whether the current step is done correctly."""
        result = await self.run_check("voice")
        if result is None:
            return "No guide is active, so there is no step to check."
        return json.dumps(result.to_dict())

    @function_tool()
    async def point_to_part(self, context: RunContext) -> str:
        """Find the part for the current step in the camera view and highlight it on the user's screen."""
        if not self.tracker.active:
            return "No guide is active."
        pointer = await self.run_locate("voice")
        if pointer is None:
            return "Couldn't look at the camera right now."
        if not pointer.found:
            return "The part isn't visible. Ask the user to move the camera so the whole area is in view."
        return f"Highlighted the {pointer.label} on the user's screen with a box. Tell them to look at the box."

    @function_tool()
    async def stop_guide(self, context: RunContext) -> str:
        """Stop the current guide, for example if the user wants a different repair."""
        self.tracker.stop()
        self.log.write("guide_stopped")
        await self.publish_state()
        return "Guide stopped."


async def watch(agent: Handy, session: AgentSession) -> None:
    """Every few seconds, quietly check the current step and speak up if something looks wrong."""
    while True:
        await asyncio.sleep(WATCH_INTERVAL_S)
        if not agent.tracker.active or agent._check_lock.locked():
            continue
        if session.agent_state == "speaking":
            continue
        result = await agent.run_check("watcher")
        if result is None or result.verdict != "wrong" or result.confidence < WARN_CONFIDENCE:
            continue
        if result.reason == agent._last_warning:
            continue  # don't nag about the same thing twice
        agent._last_warning = result.reason
        session.generate_reply(
            instructions=(
                f"Interrupt politely: something looks wrong on this step. What you see: {result.reason}. "
                f"Tell the user: {result.tip}"
            )
        )


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    index = GuideIndex(load_guides())
    if not index.guides:
        logger.warning("No guides loaded. Run `python -m handy.ingest` first.")
    log = EventLog(ctx.room.name)
    if setup_langfuse(ctx.room.name):
        log.write("tracing", backend="langfuse")
    log.write("session_started", guides=len(index.guides), hybrid=index.has_embeddings)

    agent = Handy(ctx.room, index, log)
    session = AgentSession(llm=google.realtime.RealtimeModel(model=LIVE_MODEL, voice="Puck"))

    # Buttons in the web app call these over RPC. After each, the agent says the new step.
    async def on_button(action: str) -> str:
        if action == "point":
            await agent.run_locate("button")
            return "ok"
        if action == "check":
            result = await agent.run_check("button")
            if result:
                session.generate_reply(
                    instructions=f"Tell the user the check result in one sentence: {json.dumps(result.to_dict())}"
                )
            return "ok"
        text = await agent.move(action)
        session.generate_reply(instructions=f"Read this to the user in your own words: {text}")
        return "ok"

    lp = ctx.room.local_participant

    @lp.register_rpc_method("handy.next")
    async def _next(data: rtc.RpcInvocationData) -> str:
        return await on_button("next")

    @lp.register_rpc_method("handy.previous")
    async def _previous(data: rtc.RpcInvocationData) -> str:
        return await on_button("previous")

    @lp.register_rpc_method("handy.check")
    async def _check(data: rtc.RpcInvocationData) -> str:
        return await on_button("check")

    @lp.register_rpc_method("handy.point")
    async def _point(data: rtc.RpcInvocationData) -> str:
        return await on_button("point")

    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(video_input=True),
    )

    watcher = asyncio.create_task(watch(agent, session)) if WATCH_INTERVAL_S > 0 else None

    async def cleanup() -> None:
        if watcher:
            watcher.cancel()
        if agent._locate_task:
            agent._locate_task.cancel()
        await agent.frames.aclose()
        log.write("session_ended")

    ctx.add_shutdown_callback(cleanup)

    # The web app can ask for a language through the participant's metadata.
    user = await ctx.wait_for_participant()
    language = ""
    try:
        language = json.loads(user.metadata or "{}").get("language", "")
    except json.JSONDecodeError:
        pass
    if language:
        await agent.update_instructions(f"{INSTRUCTIONS}\nAlways speak {language}, whatever language the guide is in.")
        log.write("language", language=language)

    await session.generate_reply(
        instructions="Greet the user in one sentence and ask what they'd like to fix on their laptop."
    )
