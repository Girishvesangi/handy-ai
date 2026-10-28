"""Usage and latency stats from real sessions (the JSONL files in agent/logs/)."""

from __future__ import annotations

from collections import Counter

from handy.eventlog import read_events

from .metrics import percentile


def run() -> dict:
    events = read_events()
    by_type = Counter(e["event"] for e in events)
    checks = [e for e in events if e["event"] == "check"]
    searches = [e for e in events if e["event"] == "search"]
    return {
        "sessions": len({e["session"] for e in events}),
        "guides_started": by_type["guide_started"],
        "guides_finished": by_type["guide_finished"],
        "steps_moved": by_type["step"],
        "checks": len(checks),
        "check_verdicts": dict(Counter(e["verdict"] for e in checks)),
        "check_latency_ms": {
            "p50": percentile([e["latency_ms"] for e in checks], 50),
            "p95": percentile([e["latency_ms"] for e in checks], 95),
        },
        "search_latency_ms": {
            "p50": percentile([e["latency_ms"] for e in searches], 50),
            "p95": percentile([e["latency_ms"] for e in searches], 95),
        },
    }
