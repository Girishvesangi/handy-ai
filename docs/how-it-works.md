# How Handy works

This walks through every part of the system, in the order data flows through it. Each section ends with what to say about it in an interview.

## 1. The live connection

Three programs are involved:

| Piece | Runs on | Job |
| --- | --- | --- |
| Web app (`web/`) | The user's phone browser | Camera, mic, step card, buttons |
| LiveKit Cloud | LiveKit's servers | Relays audio, video and data between participants |
| Agent (`agent/`) | Your machine, or a server once deployed | Joins the room as a bot and runs the AI |

A **room** works like a video call. The browser joins as one participant and the agent as another. LiveKit carries the media over **WebRTC**, which is built for low delay: it sends small packets and tolerates a few lost ones, so speech never stalls waiting for a retransmit.

**Joining safely.** The browser needs a token (a signed JWT) to join a room, and the token is signed with the LiveKit API secret. That secret must never reach the browser, so `web/app/api/token/route.ts` signs a 15-minute token on the server for a fresh room called `handy-<random>`. The agent server sees the new room and joins it automatically.

*Interview angle:* why WebRTC rather than WebSockets for media, and why secrets stay on the server while short-lived tokens go to clients.

## 2. The voice: a realtime model

The classic voice pipeline chains three models: speech-to-text, an LLM, then text-to-speech. Each hop adds delay, and tone of voice is lost at the text step.

Handy uses **Gemini Live**, a realtime model that takes audio and images in and streams audio out. It decides when you have finished speaking, can be interrupted mid-sentence, and usually answers in under a second. `AgentSession` in `agent/agent.py` wires the room's audio and video to it. `room_io.RoomOptions(video_input=True)` turns on the camera feed, and LiveKit samples it at 1 frame per second while you talk and about 1 every 3 seconds when you're quiet.

The system prompt (`INSTRUCTIONS`) sets the workflow: find a guide, read steps in plain words, check work when asked. It also adds guardrails: only describe what is visible, never guess a model number, and always mention safety.

*Interview angle:* the latency and control trade-off between realtime speech-to-speech and a cascaded pipeline.

## 3. Tools: how the model takes actions

The model can't search or remember the current step by itself, so the agent gives it **tools**: Python methods marked with `@function_tool()`. LiveKit turns each method's signature and docstring into a JSON schema that the model sees. When the model decides to call one, LiveKit runs the method and sends the return value back to the model.

| Tool | What it does |
| --- | --- |
| `find_guides(query)` | Hybrid search over guides, returns the top 3 |
| `start_guide(guide_id)` | Starts the step tracker at step 1, returns the tools needed and step 1 |
| `next_step`, `previous_step`, `go_to_step`, `repeat_step` | Move through the guide |
| `check_my_work()` | Runs the step checker on the latest camera frame |
| `point_to_part()` | Finds the part for this step in the camera view and draws a box on the user's screen |
| `stop_guide()` | Ends the current guide |

After each change, the agent sends the new state to the browser as a data message on topic `handy.state`, and the step card redraws. The **Back, Check and Next buttons** go the other way. They call the agent over **RPC** (`handy.next` and so on), which runs the same code as the voice tools and then asks the model to say the new step out loud. Buttons matter because a workshop can be noisy.

*Interview angle:* tool calling, keeping the UI and the model in sync, and giving people a non-voice fallback.

## 4. Finding the right guide (RAG)

`python -m handy.ingest` runs about 30 searches against the iFixit API, such as "ThinkPad RAM replacement", downloads around 120 full guides with their steps and photos, and saves them to `agent/data/guides.json`. With `--embed`, it also stores a Gemini embedding of each guide.

`handy/search.py` combines two rankings:

- **BM25 keyword search** is good at exact model names like "A1466" or "T480", which embeddings often blur together.
- **Embedding search** handles loose phrasing, so "my laptop won't hold a charge" finds battery guides.
- **Reciprocal rank fusion (RRF)** merges them. Each ranking gives an item 1 / (60 + rank) points. This uses only rank positions, so there's no need to calibrate BM25 scores against cosine similarities.

If there are no embeddings, search falls back to BM25 alone, so the app still works without the extra step.

**Why a JSON file and not a vector database?** At a few hundred guides, the whole index fits in memory and a search takes milliseconds. A database like Postgres with pgvector only pays off at hundreds of thousands of documents or with many writers. Knowing when not to add infrastructure is itself a good interview answer.

*Interview angle:* hybrid search, RRF, and sizing infrastructure to the data.

## 5. Checking the user's work

The live model only glances at frames. For a careful verdict, `handy/checker.py` makes a separate call to **Gemini Flash** with three inputs:

1. the step's instructions
2. iFixit's reference photo for that step
3. the user's latest camera frame, from `handy/frames.py`, which keeps only the newest frame and encodes it as JPEG

It asks for structured JSON (`verdict`, `confidence`, `reason`, `tip`) using a response schema. The verdict is one of `done`, `not_done`, `wrong` or `unclear`. Anything malformed is treated as `unclear` instead of crashing the session.

**The watcher.** A background loop in `agent/agent.py` runs the checker every 8 seconds during a step. It interrupts only when the verdict is `wrong` with confidence at least 0.75, and never repeats the same warning. That's the "it caught my mistake" moment in the demo. The watcher also skips its turn while the agent is speaking or another check is running.

The checker runs beside the conversation, never in its path, so the voice stays fast while the careful check takes a second or two.

*Interview angle:* fast and slow paths, structured outputs, and tuning a confidence threshold to trade missed mistakes against false alarms.

## 6. Pointing at the part

"Which connector?" is the most common question in a repair, and words are bad at answering it. `locate_part` in `handy/checker.py` sends the latest frame and the step text to Gemini Flash and asks for a **bounding box** (`box_2d`, normalized 0 to 1000, which is Gemini's convention) around the one part to act on. The agent runs it in the background whenever a new step starts (`POINTER_AUTO`), and again when the user asks "where?" by voice or with the button.

Two details make the box land in the right place:

- **Rotation.** Phones often send frames sideways with a rotation flag rather than rotating the pixels. `handy/frames.py` turns each frame upright before encoding, and reports the upright width and height.
- **Cropping.** The web app shows the camera with `object-fit: cover`, which crops the edges to fill the screen. `PointerOverlay.tsx` redoes that crop math (scale by the larger ratio, then centre) to map the box onto screen pixels.

The box fades after 8 seconds, because the camera moves and an old box drifts off target. A box about an earlier step is dropped as soon as the step changes.

*Interview angle:* grounding (getting coordinates, not just text, from a vision model) and the unglamorous coordinate bugs that make or break a visual feature.

## 7. The rest of the experience

- **Live captions.** Gemini Live transcribes both sides. LiveKit streams the text to the room, and `Captions.tsx` shows the latest line from each speaker. This helps in a noisy room and makes the demo video readable with the sound off.
- **Tools checklist.** At step 1, the app lists the guide's tools with tick boxes, plus difficulty, time, and a power-off reminder.
- **Repair recap.** The tracker counts checks and records each mistake the checker caught. On the last step the agent sends a recap on topic `handy.recap`. If the user presses End early, the app builds the same recap from the messages it has seen.
- **Any language.** The landing page has a language picker. The choice rides in the LiveKit token's participant metadata, and the agent reads it with `ctx.wait_for_participant()` and updates its instructions. By default Handy replies in whatever language the user speaks and translates the English guides as it reads them.
- **PDF manuals.** `python -m handy.pdf_ingest` uploads a service manual to Gemini and asks for structured JSON: each procedure's title, tools, steps and start page. These become guides with negative ids, so they never clash with iFixit's.
- **Tracing.** LiveKit Agents emits OpenTelemetry spans for every turn, model call and tool call. `handy/tracing.py` sends them to Langfuse when keys are set, giving a per-session timeline of where the latency goes.

## 8. Measuring it (evals)

Every session writes a JSONL log in `agent/logs/` with each search, step change and check, with timings. The `agent/evals` package measures three things:

| Eval | Data | Metrics |
| --- | --- | --- |
| Retrieval | 33 spoken-style queries in `evals/data/retrieval_queries.jsonl` | hit@1, hit@3, MRR, keyword vs hybrid |
| Step checking | Real labeled phone photos (`evals/data/step_cases.jsonl`) plus a proxy set from iFixit photos | accuracy, mistake catch rate, false alarm rate, latency p50/p95, with and without the reference photo |
| Sessions | Your real usage logs | check and search latency, guides finished |

`python -m evals all --proxy 40` writes `web/public/eval-results.json`, which the `/evals` page displays.

Be honest about the **proxy set**. It only tests whether the checker can match a photo to its step's instructions. The number that really counts comes from about 40 labeled photos of real repairs (see `agent/evals/data/README.md`). The comparison "with reference photo vs without" is a good experiment to report.

*Interview angle:* building evals before tuning, proxy versus real metrics, and why false alarms matter as much as accuracy for an assistant that interrupts.

## 9. Testing and shipping

- `agent/tests/` holds 41 unit tests for parsing, search, the tracker, the checker, the pointer and frame rotation, PDF ingest, the eval metrics, and the agent's tools (using a fake room and a fake model). GitHub Actions runs them and builds the web app on every push.
- `agent/Dockerfile` packages the agent. See [deploy.md](deploy.md) for LiveKit Cloud or Fly.io for the agent, and Vercel for the web app.

## Ideas for next steps

- Track the pointer box between vision calls (for example with optical flow in the browser) so it follows the part as the camera moves.
- Let users upload a PDF manual from the web app, not only the command line.
- Save repair history per user so they can resume a half-finished repair.
