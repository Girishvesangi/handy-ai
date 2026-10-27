# Week 1 walkthrough: a talking camera

Goal for this week: open a web page, point the camera at a laptop, ask "what is this?", and hear a spoken answer. This file explains every piece so you can describe it in an interview.

## The big picture

Three programs talk to each other:

| Piece | Where it runs | Job |
| --- | --- | --- |
| Web page (`web/`) | Your browser | Turns on the camera and mic, joins a room |
| LiveKit Cloud | LiveKit's servers | Relays live audio and video between everyone in a room |
| Agent (`agent/`) | Your laptop for now, a server later | Joins the room as a bot, talks to Gemini Live |

A **room** is like a video call. Your browser joins as one participant and the agent joins as another. LiveKit moves the media between them using **WebRTC**, the same technology behind Google Meet. It is built for low delay: it sends small packets and tolerates a few getting lost, so a conversation never stalls.

The flow of one question:

1. You say "what is this?" The mic audio streams to LiveKit, and on to the agent.
2. The agent forwards the audio, plus the latest camera frame (about one per second), to Gemini Live over a WebSocket.
3. Gemini Live decides you have finished talking, looks at the frame, and streams back spoken audio.
4. The agent publishes that audio into the room, and your browser plays it.

## Why a "realtime" model?

The classic voice pipeline has three models: speech-to-text, then an LLM, then text-to-speech. Each step adds delay, and tone of voice is lost in the text step.

A **realtime model** like Gemini Live takes audio (and images) in and gives audio out directly. That means:

- lower latency, often under a second
- natural interruptions: if you talk over it, it stops
- one API to manage instead of three

The trade-off is less control over each step. In week 4 the step checker will be a separate, slower, more careful vision call, so we get both speed and accuracy.

## `agent/agent.py`, line by line

```python
server = AgentServer()
```
The **worker**. It keeps a connection open to LiveKit Cloud and waits for jobs. When a new room is created, LiveKit sends the worker a job, and the worker starts your function for that room. One worker can handle many rooms at once, each in its own process.

```python
@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
```
The function that runs once per room. `ctx.room` is the room the agent just joined. It is `async` because the agent waits on the network all the time, and async lets one process juggle many waits without blocking.

```python
session = AgentSession(llm=google.realtime.RealtimeModel(voice="Puck"))
```
An **AgentSession** is the conversation loop: it reads input from the room, passes it to the model, and sends the output back. Here the only model is Gemini Live. `voice` picks one of Gemini's voices. The API key is read from the `GOOGLE_API_KEY` environment variable.

```python
await session.start(
    agent=Handy(),
    room=ctx.room,
    room_options=room_io.RoomOptions(video_input=True),
)
```
`Handy` holds the **instructions** (the system prompt). `video_input=True` is the key line for us: without it the agent only hears you. With it, frames from your camera track are sampled and sent to the model. By default LiveKit sends 1 frame per second while you are talking and about 1 frame every 3 seconds when you are quiet, which keeps cost and latency down.

```python
await session.generate_reply(instructions="Greet the user ...")
```
Makes the agent speak first, so you know it is connected.

**The instructions** (`INSTRUCTIONS`) do three things worth noticing:
- they tell the model to describe only what it can see, and to say when it is unsure instead of guessing a model number (this reduces hallucination)
- they keep answers short, since long answers feel slow when spoken
- they add a safety reminder about unplugging before opening a laptop

## `web/app/api/token/route.ts`

To join a room, a browser needs a **token**: a signed JWT that says "this person may join room X for 15 minutes". The token is signed with your LiveKit **API secret**.

The secret must never reach the browser, because anyone with it could create tokens for any room. So the browser asks our own server (`POST /api/token`), the server signs the token, and only the token goes back. This pattern (secret on the server, short-lived token to the client) is how almost every real-time and payment API works. It's a common interview question.

Each call creates a new room named `handy-<random>`, so every session is private and the agent joins it automatically.

## `web/app/page.tsx`

- `start()` fetches a token, then renders `<LiveKitRoom>` with it.
- `<LiveKitRoom audio video={{ facingMode: "environment" }}>` connects and publishes your mic and camera. `"environment"` asks a phone for the back camera, the one you point at things.
- `useVoiceAssistant()` gives the agent's state (`listening`, `thinking`, `speaking`), which we show on screen.
- `<VideoTrack>` shows your own camera so you can aim it.
- `<RoomAudioRenderer>` plays the agent's voice.

## Things to try once it runs

1. Point at the bottom of a laptop and ask "how many screws can you see?" Is it right?
2. Ask about a part with a label (RAM stick, SSD). Can it read the label? What if you move closer?
3. Interrupt it mid-sentence. Does it stop?
4. Point at something that is not a laptop. Does it say so, or make things up?

Write down what goes wrong. Those failures are the start of your eval set in week 5.

## Interview talking points from this week

- Realtime speech-to-speech models versus a speech-to-text, LLM, text-to-speech pipeline, and the latency trade-off
- Why WebRTC instead of plain HTTP or WebSockets for live media
- Token-based auth: keeping the API secret on the server
- Sampling video at about 1 frame per second to control cost and latency
