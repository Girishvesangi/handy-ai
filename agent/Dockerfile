# Container for the Handy agent. Works with LiveKit Cloud agent hosting
# (`lk agent create`) or any container host such as Fly.io or Railway.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Guides must exist in the image: run `python -m handy.ingest --embed` before building.
RUN test -f data/guides.json || (echo "data/guides.json missing: run python -m handy.ingest first" && exit 1)

CMD ["python", "-m", "livekit.agents", "start", "agent.py"]
