"""Handy, week 1: a voice agent that can see your camera.

The agent joins a LiveKit room, listens to the user's microphone, watches
their camera (about one frame per second), and answers out loud using the
Gemini Live API.

Run it with:  python -m livekit.agents start agent.py --dev --log-format colored
"""

import os

from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, room_io
from livekit.plugins import google

load_dotenv()

INSTRUCTIONS = """
You are Handy, a friendly and patient laptop repair helper.
The user is pointing their phone camera at a laptop or a laptop part.
- When asked what something is, describe what you can actually see:
  the brand and model if visible, and the parts in view (screws, cover,
  battery, RAM, SSD, fan, cables).
- If you are not sure, say so and ask the user to move the camera closer
  or show a label. Never guess a model number.
- Keep answers short and spoken-friendly: one to three sentences.
- Safety first: if the user is about to open a laptop, remind them to
  shut it down and unplug the charger.
"""


class Handy(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=INSTRUCTIONS)


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    # Gemini Live hears audio and sees images directly, so we don't need
    # separate speech-to-text or text-to-speech models.
    model_kwargs = {}
    if os.getenv("GEMINI_LIVE_MODEL"):
        model_kwargs["model"] = os.environ["GEMINI_LIVE_MODEL"]

    session = AgentSession(
        llm=google.realtime.RealtimeModel(voice="Puck", **model_kwargs),
    )

    await session.start(
        agent=Handy(),
        room=ctx.room,
        # video_input=True forwards the user's camera track to the model.
        room_options=room_io.RoomOptions(video_input=True),
    )

    await session.generate_reply(
        instructions="Greet the user in one sentence and ask them to show you their laptop."
    )
