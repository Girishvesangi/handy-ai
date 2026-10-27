# Handy

A live voice and camera copilot for laptop repairs. Point your phone at a laptop, talk to it, and Handy walks you through the official repair guide step by step and checks each step as you go.

**Status: week 1.** Handy can see your camera and answer questions by voice ("what is this?"). Guide search, step tracking, and step checking come in later weeks.

## How it works

```
phone browser ──WebRTC──> LiveKit Cloud <──WebRTC── Python agent ──> Gemini Live API
 (camera + mic)            (media relay)            (joins the room)   (hears + sees, talks back)
```

- `web/` is a Next.js page. It gets a token from its own `/api/token` route, joins a LiveKit room, and publishes your camera and mic.
- `agent/` is a LiveKit Agents worker. It joins every new room, forwards your audio and about one camera frame per second to Gemini Live, and plays the spoken answer back.

See [docs/week1.md](docs/week1.md) for a file-by-file walkthrough.

## Run it locally

You need Python 3.10+, Node 20+, a [LiveKit Cloud](https://cloud.livekit.io) project, and a [Gemini API key](https://aistudio.google.com/apikey).

**1. Start the agent**

```bash
cd agent
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in your keys
python -m livekit.agents start agent.py --dev --log-format colored
```

**2. Start the web app** (in a second terminal)

```bash
cd web
npm install
cp .env.example .env.local         # same LiveKit values as agent/.env
npm run dev
```

Open http://localhost:3000 on your laptop, press **Start**, allow the camera and mic, and ask "what is this?".

**Trying it on your phone:** phone browsers only allow the camera on `https` pages. The quickest way is a tunnel, for example `npx localtunnel --port 3000` or `cloudflared tunnel --url http://localhost:3000`, then open the https link it prints on your phone. Deploying to Vercel (week 6) removes this step.

## Roadmap

1. Week 1: voice and camera demo (this)
2. Week 2: guide search over iFixit laptop guides
3. Week 3: step-by-step walkthrough
4. Week 4: step checker (is this step done right?)
5. Week 5: eval suite and published accuracy numbers
6. Week 6: deploy, tracing, demo video

Repair guides come from [iFixit](https://www.ifixit.com) and are shared under their Creative Commons license.
