# Deploying Handy

Two things go online: the **agent** (a long-running Python worker) and the **web app** (Next.js). They never talk to each other directly. Both connect to your LiveKit Cloud project.

## Before you start

1. On your machine, in `agent/`, run `python -m handy.ingest --embed` so `agent/data/guides.json` exists. The Docker image refuses to build without it.
2. Have these values ready: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `GOOGLE_API_KEY`.

## Agent, option A: LiveKit Cloud agent hosting (simplest)

LiveKit Cloud can build and run the agent from `agent/Dockerfile`.

```bash
# install the LiveKit CLI: https://docs.livekit.io/home/cli/
lk cloud auth                     # log in to your project
cd agent
lk agent create                   # first time: builds the Dockerfile and deploys
lk agent update-secrets --secrets "GOOGLE_API_KEY=..."   # add the Gemini key
lk agent deploy                   # later deploys
lk agent logs                     # watch it run
```

LiveKit supplies the `LIVEKIT_*` variables to agents it hosts. Check the [LiveKit agent deployment docs](https://docs.livekit.io/agents/ops/deployment/) for the current commands, since the CLI changes often.

## Agent, option B: Fly.io (or any container host)

```bash
cd agent
fly launch --no-deploy            # creates fly.toml; say no to databases
fly secrets set LIVEKIT_URL=... LIVEKIT_API_KEY=... LIVEKIT_API_SECRET=... GOOGLE_API_KEY=...
fly deploy
fly logs
```

The agent needs no public port. It opens an outbound connection to LiveKit, so remove any `[http_service]` section Fly adds to `fly.toml`. Give it at least 1 GB of memory.

## Web app: Vercel

1. Import the GitHub repo in [Vercel](https://vercel.com/new) and set **Root Directory** to `web`.
2. Add the environment variables `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, and optionally `ACCESS_CODE`.
3. Deploy. You get an `https://...vercel.app` URL that works on any phone.

To show eval numbers on the live site, run `python -m evals all --proxy 40` locally, commit `web/public/eval-results.json`, and push.

## Costs at demo scale (rough, check current pricing)

- LiveKit Cloud and Vercel: free tiers cover a demo.
- Gemini: you pay for Live audio minutes plus one Flash vision call per check (about every 8 seconds during a step). Set `WATCH_INTERVAL_S=0` to turn the watcher off and only check on request.
- Fly.io: a small always-on machine costs a few dollars a month.

## Before sharing the link

- The token route hands a token to anyone who opens the site. For a public demo, set `ACCESS_CODE` in Vercel so only people you give the code to can start a session and use your Gemini quota.
- Set a budget alert in Google AI Studio or Google Cloud.
