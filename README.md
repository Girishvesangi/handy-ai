# Handy

**A live voice and camera copilot for laptop repairs.** Point your phone at a laptop and say what you want to fix. Handy finds the matching [iFixit](https://www.ifixit.com) guide, talks you through it one step at a time, and watches the camera to catch mistakes ("wait, unplug the battery connector first").

- **Real-time voice + vision**: Gemini Live hears you and sees the camera, over LiveKit WebRTC.
- **RAG over repair guides**: hybrid search (BM25 + Gemini embeddings, fused with reciprocal rank fusion) over iFixit laptop guides.
- **Agent with tools**: finds guides, tracks the current step, moves forward and back, and checks your work.
- **Step checker**: a separate vision call compares your camera frame with the guide's reference photo and returns done / not done / wrong / unclear. A background watcher runs it every few seconds and speaks up only when it is confident something is wrong.
- **Pointer**: Handy draws a box on your camera view around the part to touch next ("RAM module"), at every new step or when you ask "where is it?".
- **Live captions**, a **tools checklist** before you start, and a **repair recap** at the end (steps confirmed, time, mistakes caught).
- **Any language**: speak in your language, or pick one, and Handy translates the English guides as it reads them.
- **Bring your own manual**: turn a PDF service manual (Dell, Lenovo, HP...) into step-by-step guides with one command.
- **Evals**: retrieval hit@k and MRR, step-check accuracy, mistake catch rate, false alarm rate, and latency, shown on an `/evals` page.
- **Tracing** (optional): send every session's timeline to Langfuse through OpenTelemetry.

## How it works

```
 phone browser (Next.js)                     Python agent (LiveKit Agents)
 ┌───────────────────────┐   WebRTC via   ┌──────────────────────────────────────┐
 │ camera + mic          │ ─────────────▶ │ Gemini Live (voice in/out, sees ~1fps) │
 │ step card + photo     │  LiveKit Cloud │   tools: find_guides, start_guide,    │
 │ pointer box, captions │ ◀───────────── │          next/previous/go_to_step,    │
 │ verdict, recap        │  data + RPC    │          check_my_work, point_to_part │
 │ Back/Where?/Check/Next│                │                                       │
 └───────────────────────┘                │ GuideIndex (BM25 + embeddings)        │
                                          │ StepChecker (Gemini Flash vision)     │
                                          │ watcher loop, JSONL session logs      │
                                          └──────────────────────────────────────┘
```

Read [docs/how-it-works.md](docs/how-it-works.md) for a walkthrough of every part, and [docs/deploy.md](docs/deploy.md) to put it online.

## Repo layout

| Path | What's there |
| --- | --- |
| `agent/agent.py` | The LiveKit agent: instructions, tools, RPC handlers, watcher |
| `agent/handy/` | Core logic with no LiveKit dependency: guides, iFixit client, search, tracker, checker, logs |
| `agent/evals/` | Eval harness and datasets |
| `agent/tests/` | Unit tests (`pytest`) |
| `web/` | Next.js app: token route, live session UI, `/evals` page |

## Run it locally

You need Python 3.10+, Node 20+, a [LiveKit Cloud](https://cloud.livekit.io) project (free tier), and a [Gemini API key](https://aistudio.google.com/apikey).

**1. Set up the agent and download guides**

```bash
cd agent
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                   # fill in LiveKit and Gemini keys
python -m handy.ingest --embed         # ~120 laptop guides from iFixit, takes a few minutes
python -m pytest -q                    # optional: run the tests
```

**2. Start the agent**

```bash
python -m livekit.agents start agent.py --dev --log-format colored
```

**3. Start the web app** (second terminal)

```bash
cd web
npm install
cp .env.example .env.local             # same LiveKit values as agent/.env
npm run dev
```

Open http://localhost:3000, press **Start a repair**, allow camera and mic, and say something like "I want to replace the battery on my MacBook Air".

**On your phone:** phone browsers only allow the camera on `https` pages. Run a tunnel such as `cloudflared tunnel --url http://localhost:3000` (or `npx localtunnel --port 3000`) and open the https link on your phone, or deploy (see [docs/deploy.md](docs/deploy.md)).

## Add a PDF service manual

```bash
cd agent
python -m handy.pdf_ingest ~/Downloads/latitude-5490-manual.pdf --device "Dell Latitude 5490" --url https://link-to-the-manual.pdf
```

Gemini reads the manual, pulls out each removal procedure as a guide, and adds them to `data/guides.json` next to the iFixit guides. Restart the agent to use them.

## Evals

```bash
cd agent
python -m evals retrieval              # guide search: hit@1, hit@3, MRR (keyword vs hybrid)
python -m evals steps --proxy 40       # step checker on a proxy set built from iFixit photos
python -m evals stats                  # latency and usage from your real sessions (agent/logs)
python -m evals all --proxy 40         # all of the above, published to web/public for /evals
```

The proxy set only tests whether the checker can match a photo to its step. Real accuracy needs labeled photos of real repairs: see [agent/evals/data/README.md](agent/evals/data/README.md).

## Configuration

All settings live in `agent/.env` (see `.env.example`): the models (`GEMINI_LIVE_MODEL`, `CHECKER_MODEL`, `EMBED_MODEL`), how often the watcher checks (`WATCH_INTERVAL_S`, `0` turns it off), how confident it must be before interrupting (`WARN_CONFIDENCE`), whether to point at parts automatically (`POINTER_AUTO`), and Langfuse keys for tracing. The web app takes an optional `ACCESS_CODE` in `web/.env.local`.

## Credits and license

Repair guides and photos come from [iFixit](https://www.ifixit.com) under [CC BY-NC-SA](https://creativecommons.org/licenses/by-nc-sa/3.0/). Handy credits iFixit on every step card and is a non-commercial project.

Always shut down and unplug a laptop before opening it, and never puncture or bend a lithium battery.
