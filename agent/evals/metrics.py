"""Small, dependency-free metric helpers shared by the eval scripts."""

from __future__ import annotations

from collections import Counter


def hit_at_k(ranks: list[int | None], k: int) -> float:
    """Share of queries whose first relevant result is in the top k. Ranks are 1-based, None = missed."""
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks) if ranks else 0.0


def mrr(ranks: list[int | None]) -> float:
    return sum(1 / r for r in ranks if r) / len(ranks) if ranks else 0.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    i = min(len(s) - 1, max(0, round(p / 100 * (len(s) - 1))))
    return s[i]


def confusion(labels: list[str], preds: list[str], classes: list[str]) -> dict[str, dict[str, int]]:
    counts = Counter(zip(labels, preds))
    return {t: {p: counts[(t, p)] for p in classes} for t in classes}


def classification_report(labels: list[str], preds: list[str], classes: list[str]) -> dict:
    n = len(labels)
    accuracy = sum(1 for t, p in zip(labels, preds) if t == p) / n if n else 0.0
    per_class = {}
    for c in classes:
        tp = sum(1 for t, p in zip(labels, preds) if t == c and p == c)
        fp = sum(1 for t, p in zip(labels, preds) if t != c and p == c)
        fn = sum(1 for t, p in zip(labels, preds) if t == c and p != c)
        per_class[c] = {
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "support": sum(1 for t in labels if t == c),
        }
    # How often a correctly done step gets flagged as wrong: the "annoying" metric.
    done_total = sum(1 for t in labels if t == "done")
    false_alarms = sum(1 for t, p in zip(labels, preds) if t == "done" and p == "wrong")
    return {
        "n": n,
        "accuracy": accuracy,
        "per_class": per_class,
        "false_alarm_rate": false_alarms / done_total if done_total else 0.0,
        "mistake_catch_rate": per_class.get("wrong", {}).get("recall", 0.0),
        "confusion": confusion(labels, preds, classes),
    }
